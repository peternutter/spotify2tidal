"""
Main sync engine for transferring from Spotify to Tidal.
"""

import logging
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import spotipy
import tidalapi
from tqdm import tqdm

from .cache import MatchCache
from .library import LibraryExporter
from .matching import TrackMatcher, normalize, simplify
from .rate_limiter import RateLimiter
from .searcher import TidalSearcher

if TYPE_CHECKING:
    from .logging_utils import SyncLogger

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["SyncEngine", "TrackMatcher", "normalize", "simplify"]


class SyncEngine:
    """Main sync engine for transferring from Spotify to Tidal."""

    def __init__(
        self,
        spotify: spotipy.Spotify,
        tidal: tidalapi.Session,
        max_concurrent: int = 10,
        rate_limit: float = 10,
        library_dir: str = "./library",
        logger: Optional["SyncLogger"] = None,
        cache: Optional[MatchCache] = None,
        progress_callback=None,
    ):
        self.spotify = spotify
        self.tidal = tidal
        self.cache = cache or MatchCache()
        self.rate_limiter = RateLimiter(max_concurrent, rate_limit)
        self.searcher = TidalSearcher(tidal, self.cache, self.rate_limiter)
        self.library = LibraryExporter(library_dir)
        self._logger = logger
        self._progress_callback = progress_callback

    def _log(self, level: str, message: str):
        """Log a message using the provided logger or fallback to print."""
        if self._logger:
            getattr(self._logger, level)(message)
        else:
            # Fallback to print for backwards compatibility
            print(message)

    def _report_progress(self, **kwargs):
        """Report progress to callback if available."""
        if self._progress_callback:
            self._progress_callback(**kwargs)

    def _progress_iter(self, iterable, desc: str, phase: str = "searching"):
        """
        Create a progress iterator that works for both CLI (tqdm) and webapp.

        Wraps tqdm but also reports progress via callback for webapp updates.
        """
        items = list(iterable)
        total = len(items)

        # Report initial state
        self._report_progress(event="phase", phase=phase)
        self._report_progress(event="total", total=total)
        self._report_progress(event="update", current=0, total=total, phase=phase)

        # Use tqdm for CLI progress bar
        for i, item in enumerate(tqdm(items, desc=desc)):
            yield item

            # Report progress to webapp callback (every item for responsive UI)
            self._report_progress(
                event="update", current=i + 1, total=total, phase=phase
            )

    async def sync_playlist(
        self, spotify_playlist_id: str, tidal_playlist_id: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Sync a Spotify playlist to Tidal.

        Returns: (tracks_added, tracks_not_found)
        """
        self.rate_limiter.start()
        try:
            # Report fetching phase
            self._report_progress(event="phase", phase="fetching")

            # Get Spotify tracks
            spotify_tracks = await self._get_spotify_playlist_tracks(
                spotify_playlist_id
            )
            playlist_name = self.spotify.playlist(spotify_playlist_id)["name"]
            logger.info(
                f"Found {len(spotify_tracks)} tracks in Spotify playlist "
                f"'{playlist_name}'"
            )

            if not spotify_tracks:
                return 0, 0

            # Get or create Tidal playlist
            if tidal_playlist_id:
                tidal_playlist = self.tidal.playlist(tidal_playlist_id)
            else:
                # Find existing or create new
                tidal_playlist = await self._get_or_create_tidal_playlist(playlist_name)

            # Get existing Tidal tracks (paginated for large playlists)
            existing_tidal_ids = set()
            if tidal_playlist.num_tracks > 0:
                existing_tidal_ids = await self._get_all_tidal_playlist_track_ids(
                    tidal_playlist
                )
                logger.info(
                    f"Found {len(existing_tidal_ids)} existing tracks in Tidal playlist"
                )

            # Save all tracks to library export
            self.library.add_tracks(spotify_tracks)

            # Search for tracks on Tidal - use progress tracking
            tidal_track_ids = []
            not_found = []
            not_found_tracks = []

            for spotify_track in self._progress_iter(
                spotify_tracks, f"Searching: {playlist_name[:20]}", phase="searching"
            ):
                tidal_id = await self.searcher.search_track(spotify_track)
                if tidal_id:
                    tidal_track_ids.append(tidal_id)
                    self._report_progress(event="item", matched=True)
                else:
                    artist = spotify_track["artists"][0]["name"]
                    name = spotify_track["name"]
                    not_found.append(f"{artist} - {name}")
                    not_found_tracks.append(spotify_track)
                    self._report_progress(event="item", matched=False)

            # Record not-found tracks for export
            for track in not_found_tracks:
                self.library.add_not_found_track(track)

            # Add only new tracks
            new_ids = [tid for tid in tidal_track_ids if tid not in existing_tidal_ids]

            if new_ids:
                # Add in chunks with progress
                chunk_size = 50
                chunks = [
                    new_ids[i : i + chunk_size]
                    for i in range(0, len(new_ids), chunk_size)
                ]
                for chunk in self._progress_iter(
                    chunks, "Adding to playlist", phase="adding"
                ):
                    tidal_playlist.add(chunk)
                logger.info(f"Added {len(new_ids)} new tracks to Tidal playlist")
            else:
                logger.info("No new tracks to add")

            if not_found:
                logger.warning(f"Could not find {len(not_found)} tracks:")
                for track in not_found[:10]:  # Show first 10
                    logger.warning(f"  - {track}")
                if len(not_found) > 10:
                    logger.warning(f"  ... and {len(not_found) - 10} more")

            return len(new_ids), len(not_found)

        finally:
            self.rate_limiter.stop()

    async def sync_favorites(self) -> Tuple[int, int]:
        """
        Sync saved/liked tracks from Spotify to Tidal favorites.

        Items are added oldest-first so they appear at the bottom in Tidal,
        preserving the chronological order from Spotify.
        """
        self.rate_limiter.start()
        try:
            # Report fetching phase
            self._report_progress(event="phase", phase="fetching")

            # Get Spotify saved tracks (returned newest-first)
            spotify_tracks = await self._get_spotify_saved_tracks()
            logger.info(f"Found {len(spotify_tracks)} saved tracks on Spotify")

            if not spotify_tracks:
                return 0, 0

            # Reverse to add oldest first (so they end up at bottom in Tidal)
            spotify_tracks = list(reversed(spotify_tracks))

            # Get existing Tidal favorites (paginated - must get all pages)
            existing_ids = await self._get_all_tidal_favorite_track_ids()
            logger.info(f"Found {len(existing_ids)} existing favorite tracks on Tidal")

            # Save all tracks to library export
            self.library.add_tracks(spotify_tracks)

            # Search and add with progress tracking
            tracks_to_add = []
            not_found_list = []
            matched = 0
            not_found = 0

            # Search tracks with progress updates
            for spotify_track in self._progress_iter(
                spotify_tracks, "Searching tracks", phase="searching"
            ):
                spotify_id = spotify_track.get("id")
                from_cache = self.cache.get_track_match(spotify_id) is not None

                tidal_id = await self.searcher.search_track(spotify_track)

                if tidal_id:
                    matched += 1
                    if tidal_id not in existing_ids:
                        tracks_to_add.append(tidal_id)
                    self._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                else:
                    not_found += 1
                    not_found_list.append(spotify_track)
                    self._report_progress(event="item", matched=False, from_cache=False)

            # Record not-found tracks for export
            for track in not_found_list:
                self.library.add_not_found_track(track)

            # Report adding phase
            if tracks_to_add:
                added = 0
                for tidal_id in self._progress_iter(
                    tracks_to_add, "Adding tracks", phase="adding"
                ):
                    try:
                        self.tidal.user.favorites.add_track(tidal_id)
                        added += 1
                    except Exception as e:
                        logger.warning(f"Failed to add track: {e}")
            else:
                added = 0

            logger.info(
                f"Added {added} tracks to Tidal favorites, {not_found} not found"
            )
            return added, not_found

        finally:
            self.rate_limiter.stop()

    async def sync_albums(self) -> Tuple[int, int]:
        """
        Sync saved albums from Spotify to Tidal.

        Albums are added oldest-first so they appear at the bottom in Tidal,
        preserving the chronological order from Spotify.
        """
        self.rate_limiter.start()
        try:
            # Report fetching phase
            self._report_progress(event="phase", phase="fetching")

            # Get Spotify saved albums (returned newest-first)
            spotify_albums = await self._get_spotify_saved_albums()
            logger.info(f"Found {len(spotify_albums)} saved albums on Spotify")

            # Reverse to add oldest first (so they end up at bottom in Tidal)
            spotify_albums = list(reversed(spotify_albums))

            # Get existing Tidal album favorites (paginated)
            existing_album_ids = await self._get_all_tidal_favorite_album_ids()
            logger.info(
                f"Found {len(existing_album_ids)} existing album favorites on Tidal"
            )

            # Save all albums to library export
            self.library.add_albums(spotify_albums)

            added = 0
            not_found = 0
            skipped = 0

            for album in self._progress_iter(
                spotify_albums, "Syncing albums", phase="searching"
            ):
                # Skip albums with missing data (removed from Spotify catalog)
                album_data = album.get("album")
                if not album_data or not album_data.get("artists"):
                    logger.warning("Skipping album with missing data")
                    not_found += 1
                    self._report_progress(event="item", matched=False)
                    continue

                spotify_id = album_data.get("id")
                from_cache = self.cache.get_album_match(spotify_id) is not None

                tidal_id = await self.searcher.search_album(album_data)
                if tidal_id:
                    self._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                    if tidal_id in existing_album_ids:
                        skipped += 1
                        continue  # Already in Tidal favorites
                    try:
                        self.tidal.user.favorites.add_album(tidal_id)
                        added += 1
                    except Exception as e:
                        logger.warning(f"Failed to add album: {e}")
                else:
                    not_found += 1
                    self._report_progress(event="item", matched=False)
                    self.library.add_not_found_album(album)
                    artist_name = album_data.get("artists", [{}])[0].get(
                        "name", "Unknown"
                    )
                    album_name = album_data.get("name", "Unknown")
                    logger.warning(f"Album not found: {artist_name} - {album_name}")

            logger.info(
                f"Albums: {added} added, {skipped} existed, {not_found} not found"
            )
            return added, not_found

        finally:
            self.rate_limiter.stop()

    async def sync_artists(self) -> Tuple[int, int]:
        """
        Sync followed artists from Spotify to Tidal.

        Artists are added oldest-first so they appear at the bottom in Tidal,
        preserving the chronological order from Spotify.
        """
        self.rate_limiter.start()
        try:
            # Report fetching phase
            self._report_progress(event="phase", phase="fetching")

            # Get Spotify followed artists (returned in an order we'll reverse)
            spotify_artists = await self._get_spotify_followed_artists()
            logger.info(f"Found {len(spotify_artists)} followed artists on Spotify")

            # Reverse to add oldest first (so they end up at bottom in Tidal)
            spotify_artists = list(reversed(spotify_artists))

            # Get existing Tidal artist favorites (paginated)
            existing_artist_ids = await self._get_all_tidal_favorite_artist_ids()
            logger.info(
                f"Found {len(existing_artist_ids)} existing artist favorites on Tidal"
            )

            # Save all artists to library export
            self.library.add_artists(spotify_artists)

            added = 0
            not_found = 0
            skipped = 0

            for artist in self._progress_iter(
                spotify_artists, "Syncing artists", phase="searching"
            ):
                spotify_id = artist.get("id")
                from_cache = self.cache.get_artist_match(spotify_id) is not None

                tidal_id = await self.searcher.search_artist(artist)
                if tidal_id:
                    self._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                    if tidal_id in existing_artist_ids:
                        skipped += 1
                        continue  # Already in Tidal favorites
                    try:
                        self.tidal.user.favorites.add_artist(tidal_id)
                        added += 1
                    except Exception as e:
                        logger.warning(f"Failed to add artist: {e}")
                else:
                    not_found += 1
                    self._report_progress(event="item", matched=False)
                    self.library.add_not_found_artist(artist)
                    logger.warning(f"Artist not found: {artist['name']}")

            logger.info(
                f"Artists: {added} added, {skipped} existed, {not_found} not found"
            )
            return added, not_found

        finally:
            self.rate_limiter.stop()

    async def sync_all_playlists(self) -> dict:
        """Sync all user playlists from Spotify to Tidal."""
        playlists = self.spotify.current_user_playlists()
        user_id = self.spotify.current_user()["id"]

        results = {}
        for playlist in playlists["items"]:
            if playlist["owner"]["id"] != user_id:
                continue  # Skip playlists not owned by user

            logger.info(f"Syncing playlist: {playlist['name']}")
            added, not_found = await self.sync_playlist(playlist["id"])
            results[playlist["name"]] = {"added": added, "not_found": not_found}

        return results

    async def export_podcasts(self) -> int:
        """
        Export saved podcasts/shows from Spotify to CSV.

        Note: Tidal doesn't support podcasts, so this is export-only.
        Returns the number of podcasts exported.
        """
        # Get Spotify saved shows
        podcasts = await self._get_spotify_saved_shows()
        logger.info(f"Found {len(podcasts)} saved podcasts/shows on Spotify")

        if podcasts:
            self.library.add_podcasts(podcasts)

        return len(podcasts)

    async def _get_spotify_saved_shows(self) -> List[dict]:
        """Get all saved shows/podcasts from Spotify."""
        shows = []
        try:
            results = self.spotify.current_user_saved_shows()

            while True:
                shows.extend(results["items"])
                self._log("progress", f"Fetching saved podcasts: {len(shows)} shows...")

                if not results["next"]:
                    break
                results = self.spotify.next(results)
        except Exception as e:
            logger.warning(f"Could not fetch podcasts (may need to re-auth): {e}")

        return shows

    async def _get_spotify_playlist_tracks(self, playlist_id: str) -> List[dict]:
        """Get all tracks from a Spotify playlist."""
        tracks = []
        results = self.spotify.playlist_tracks(playlist_id)

        while True:
            for item in results["items"]:
                if item["track"] and item["track"].get("type") == "track":
                    tracks.append(item["track"])

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return tracks

    async def _get_spotify_saved_tracks(self) -> List[dict]:
        """Get all saved/liked tracks from Spotify."""
        tracks = []
        results = self.spotify.current_user_saved_tracks()
        page = 1

        while True:
            for item in results["items"]:
                if item["track"]:
                    tracks.append(item["track"])

            self._log("progress", f"Fetching saved tracks: {len(tracks)} tracks...")

            if not results["next"]:
                break
            results = self.spotify.next(results)
            page += 1

        return tracks

    async def _get_spotify_saved_albums(self) -> List[dict]:
        """Get all saved albums from Spotify."""
        albums = []
        results = self.spotify.current_user_saved_albums()

        while True:
            albums.extend(results["items"])
            self._log("progress", f"Fetching saved albums: {len(albums)} albums...")

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return albums

    async def _get_spotify_followed_artists(self) -> List[dict]:
        """Get all followed artists from Spotify."""
        artists = []
        results = self.spotify.current_user_followed_artists()["artists"]

        while True:
            artists.extend(results["items"])
            msg = f"Fetching followed artists: {len(artists)} artists..."
            self._log("progress", msg)

            if not results["next"]:
                break
            results = self.spotify.next(results)["artists"]

        return artists

    async def _get_all_tidal_favorite_track_ids(self) -> Set[int]:
        """
        Get ALL favorite track IDs from Tidal with proper pagination.

        Tidal's favorites.tracks() only returns the first page (~100 items).
        We need to paginate to get all favorites for proper duplicate detection.
        """
        all_ids = set()
        limit = 100
        offset = 0

        while True:
            # Tidal favorites.tracks() accepts limit and offset
            page = self.tidal.user.favorites.tracks(limit=limit, offset=offset)
            if not page:
                break

            for track in page:
                all_ids.add(track.id)

            self._log("progress", f"Fetching Tidal favorites: {len(all_ids)} tracks...")

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def _get_all_tidal_favorite_album_ids(self) -> Set[int]:
        """
        Get ALL favorite album IDs from Tidal with proper pagination.
        """
        all_ids = set()
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.albums(limit=limit, offset=offset)
            if not page:
                break

            for album in page:
                all_ids.add(album.id)

            msg = f"Fetching Tidal album favorites: {len(all_ids)} albums..."
            self._log("progress", msg)

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def _get_all_tidal_favorite_artist_ids(self) -> Set[int]:
        """
        Get ALL favorite artist IDs from Tidal with proper pagination.
        """
        all_ids = set()
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.artists(limit=limit, offset=offset)
            if not page:
                break

            for artist in page:
                all_ids.add(artist.id)

            msg = f"Fetching Tidal artist favorites: {len(all_ids)} artists..."
            self._log("progress", msg)

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def _get_all_tidal_playlist_track_ids(
        self, playlist: tidalapi.Playlist
    ) -> Set[int]:
        """
        Get ALL track IDs from a Tidal playlist with proper pagination.
        """
        all_ids = set()
        limit = 100
        offset = 0

        while True:
            page = playlist.tracks(limit=limit, offset=offset)
            if not page:
                break

            for track in page:
                all_ids.add(track.id)

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def _get_or_create_tidal_playlist(self, name: str) -> tidalapi.Playlist:
        """Find existing playlist by name or create new one."""
        playlists = self.tidal.user.playlists()
        for playlist in playlists:
            if playlist.name == name:
                return playlist

        return self.tidal.user.create_playlist(name, "")

    def export_library(self) -> dict:
        """
        Export collected library data to CSV files.

        Returns dict with paths to created files and statistics.
        """
        stats = self.library.get_stats()
        logger.info(f"Library stats: {stats}")

        if any(stats.values()):
            exported = self.library.export_all()
            logger.info(f"Exported library data to: {self.library.export_dir}")
            for name, path in exported.items():
                logger.info(f"  - {name}: {path}")
            return {"files": exported, "stats": stats}
        else:
            logger.info("No library data to export")
            return {"files": {}, "stats": stats}

    async def export_tidal_library(self) -> dict:
        """
        Export current Tidal library (favorites) to CSV files.

        This fetches all Tidal favorites and exports them to CSVs.
        Useful for backup or for future bidirectional sync.

        Returns dict with paths to created files.
        """
        from .library import (
            export_tidal_albums,
            export_tidal_artists,
            export_tidal_tracks,
        )

        results = {}

        # Fetch and export Tidal tracks
        self._log("progress", "Fetching Tidal favorite tracks...")
        tracks = []
        limit = 100
        offset = 0
        while True:
            page = self.tidal.user.favorites.tracks(limit=limit, offset=offset)
            if not page:
                break
            tracks.extend(page)
            self._log("progress", f"Fetching Tidal tracks: {len(tracks)}...")
            if len(page) < limit:
                break
            offset += limit

        if tracks:
            results["tidal_tracks"] = export_tidal_tracks(
                tracks, self.library.export_dir
            )
            logger.info(f"Exported {len(tracks)} Tidal tracks")

        # Fetch and export Tidal albums
        self._log("progress", "Fetching Tidal favorite albums...")
        albums = []
        offset = 0
        while True:
            page = self.tidal.user.favorites.albums(limit=limit, offset=offset)
            if not page:
                break
            albums.extend(page)
            self._log("progress", f"Fetching Tidal albums: {len(albums)}...")
            if len(page) < limit:
                break
            offset += limit

        if albums:
            results["tidal_albums"] = export_tidal_albums(
                albums, self.library.export_dir
            )
            logger.info(f"Exported {len(albums)} Tidal albums")

        # Fetch and export Tidal artists
        self._log("progress", "Fetching Tidal favorite artists...")
        artists = []
        offset = 0
        while True:
            page = self.tidal.user.favorites.artists(limit=limit, offset=offset)
            if not page:
                break
            artists.extend(page)
            self._log("progress", f"Fetching Tidal artists: {len(artists)}...")
            if len(page) < limit:
                break
            offset += limit

        if artists:
            results["tidal_artists"] = export_tidal_artists(
                artists, self.library.export_dir
            )
            logger.info(f"Exported {len(artists)} Tidal artists")

        return results

    # =========================================================================
    # Reverse Sync: Tidal -> Spotify
    # =========================================================================

    async def sync_favorites_to_spotify(self) -> Tuple[int, int]:
        """
        Sync favorite tracks from Tidal to Spotify library.

        Returns: (tracks_added, tracks_not_found)
        """
        from .spotify_searcher import SpotifySearcher

        spotify_searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        self.rate_limiter.start()
        try:
            # Report fetching phase
            self._report_progress(event="phase", phase="fetching")

            # Get Tidal favorite tracks
            tidal_tracks = await self._get_all_tidal_favorite_tracks()
            logger.info(f"Found {len(tidal_tracks)} favorite tracks on Tidal")

            if not tidal_tracks:
                return 0, 0

            # Get existing Spotify saved track IDs
            existing_spotify_ids = await self._get_all_spotify_saved_track_ids()
            logger.info(
                f"Found {len(existing_spotify_ids)} existing saved tracks on Spotify"
            )

            # Search and collect tracks to add
            tracks_to_add = []
            not_found_count = 0

            for tidal_track in self._progress_iter(
                tidal_tracks, "Searching Spotify", phase="searching"
            ):
                tidal_id = tidal_track.id
                from_cache = self.cache.get_spotify_track_match(tidal_id) is not None

                spotify_id = await spotify_searcher.search_track(tidal_track)

                if spotify_id:
                    if spotify_id not in existing_spotify_ids:
                        tracks_to_add.append(spotify_id)
                    self._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                else:
                    not_found_count += 1
                    self._report_progress(event="item", matched=False, from_cache=False)

            # Add tracks to Spotify in batches of 50 (API limit)
            added = 0
            if tracks_to_add:
                batch_size = 50
                batches = [
                    tracks_to_add[i : i + batch_size]
                    for i in range(0, len(tracks_to_add), batch_size)
                ]

                for batch in self._progress_iter(
                    batches, "Adding to Spotify", phase="adding"
                ):
                    try:
                        self.spotify.current_user_saved_tracks_add(tracks=batch)
                        added += len(batch)
                    except Exception as e:
                        logger.warning(f"Failed to add tracks batch: {e}")

            logger.info(f"Added {added} tracks to Spotify, {not_found_count} not found")
            return added, not_found_count

        finally:
            self.rate_limiter.stop()

    async def sync_albums_to_spotify(self) -> Tuple[int, int]:
        """
        Sync favorite albums from Tidal to Spotify library.

        Returns: (albums_added, albums_not_found)
        """
        from .spotify_searcher import SpotifySearcher

        spotify_searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        self.rate_limiter.start()
        try:
            self._report_progress(event="phase", phase="fetching")

            # Get Tidal favorite albums
            tidal_albums = await self._get_all_tidal_favorite_albums()
            logger.info(f"Found {len(tidal_albums)} favorite albums on Tidal")

            if not tidal_albums:
                return 0, 0

            # Get existing Spotify saved album IDs
            existing_spotify_ids = await self._get_all_spotify_saved_album_ids()
            logger.info(f"Found {len(existing_spotify_ids)} saved albums on Spotify")

            albums_to_add = []
            not_found_count = 0

            for tidal_album in self._progress_iter(
                tidal_albums, "Searching Spotify", phase="searching"
            ):
                tidal_id = tidal_album.id
                from_cache = self.cache.get_spotify_album_match(tidal_id) is not None

                spotify_id = await spotify_searcher.search_album(tidal_album)

                if spotify_id:
                    if spotify_id not in existing_spotify_ids:
                        albums_to_add.append(spotify_id)
                    self._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                else:
                    not_found_count += 1
                    self._report_progress(event="item", matched=False, from_cache=False)

            # Add albums to Spotify in batches of 50
            added = 0
            if albums_to_add:
                batch_size = 50
                batches = [
                    albums_to_add[i : i + batch_size]
                    for i in range(0, len(albums_to_add), batch_size)
                ]

                for batch in self._progress_iter(
                    batches, "Adding to Spotify", phase="adding"
                ):
                    try:
                        self.spotify.current_user_saved_albums_add(albums=batch)
                        added += len(batch)
                    except Exception as e:
                        logger.warning(f"Failed to add albums batch: {e}")

            logger.info(f"Added {added} albums to Spotify, {not_found_count} not found")
            return added, not_found_count

        finally:
            self.rate_limiter.stop()

    async def sync_artists_to_spotify(self) -> Tuple[int, int]:
        """
        Sync followed artists from Tidal to Spotify.

        Returns: (artists_added, artists_not_found)
        """
        from .spotify_searcher import SpotifySearcher

        spotify_searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        self.rate_limiter.start()
        try:
            self._report_progress(event="phase", phase="fetching")

            # Get Tidal favorite artists
            tidal_artists = await self._get_all_tidal_favorite_artists()
            logger.info(f"Found {len(tidal_artists)} followed artists on Tidal")

            if not tidal_artists:
                return 0, 0

            # Get existing Spotify followed artist IDs
            existing_spotify_ids = await self._get_all_spotify_followed_artist_ids()
            logger.info(
                f"Found {len(existing_spotify_ids)} followed artists on Spotify"
            )

            artists_to_follow = []
            not_found_count = 0

            for tidal_artist in self._progress_iter(
                tidal_artists, "Searching Spotify", phase="searching"
            ):
                tidal_id = tidal_artist.id
                from_cache = self.cache.get_spotify_artist_match(tidal_id) is not None

                spotify_id = await spotify_searcher.search_artist(tidal_artist)

                if spotify_id:
                    if spotify_id not in existing_spotify_ids:
                        artists_to_follow.append(spotify_id)
                    self._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                else:
                    not_found_count += 1
                    self._report_progress(event="item", matched=False, from_cache=False)

            # Follow artists on Spotify in batches of 50
            added = 0
            if artists_to_follow:
                batch_size = 50
                batches = [
                    artists_to_follow[i : i + batch_size]
                    for i in range(0, len(artists_to_follow), batch_size)
                ]

                for batch in self._progress_iter(
                    batches, "Following on Spotify", phase="adding"
                ):
                    try:
                        self.spotify.user_follow_artists(ids=batch)
                        added += len(batch)
                    except Exception as e:
                        logger.warning(f"Failed to follow artists batch: {e}")

            logger.info(
                f"Followed {added} artists on Spotify, {not_found_count} not found"
            )
            return added, not_found_count

        finally:
            self.rate_limiter.stop()

    # =========================================================================
    # Helper methods for reverse sync
    # =========================================================================

    async def _get_all_tidal_favorite_tracks(self) -> list:
        """Get ALL favorite tracks from Tidal (full objects, not just IDs)."""
        all_tracks = []
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.tracks(limit=limit, offset=offset)
            if not page:
                break
            all_tracks.extend(page)
            self._log("progress", f"Fetching Tidal tracks: {len(all_tracks)}...")
            if len(page) < limit:
                break
            offset += limit

        return all_tracks

    async def _get_all_tidal_favorite_albums(self) -> list:
        """Get ALL favorite albums from Tidal (full objects, not just IDs)."""
        all_albums = []
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.albums(limit=limit, offset=offset)
            if not page:
                break
            all_albums.extend(page)
            self._log("progress", f"Fetching Tidal albums: {len(all_albums)}...")
            if len(page) < limit:
                break
            offset += limit

        return all_albums

    async def _get_all_tidal_favorite_artists(self) -> list:
        """Get ALL favorite artists from Tidal (full objects, not just IDs)."""
        all_artists = []
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.artists(limit=limit, offset=offset)
            if not page:
                break
            all_artists.extend(page)
            self._log("progress", f"Fetching Tidal artists: {len(all_artists)}...")
            if len(page) < limit:
                break
            offset += limit

        return all_artists

    async def _get_all_spotify_saved_track_ids(self) -> Set[str]:
        """Get ALL saved track IDs from Spotify."""
        all_ids = set()
        results = self.spotify.current_user_saved_tracks()

        while True:
            for item in results["items"]:
                if item["track"]:
                    all_ids.add(item["track"]["id"])

            self._log("progress", f"Fetching Spotify tracks: {len(all_ids)}...")

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return all_ids

    async def _get_all_spotify_saved_album_ids(self) -> Set[str]:
        """Get ALL saved album IDs from Spotify."""
        all_ids = set()
        results = self.spotify.current_user_saved_albums()

        while True:
            for item in results["items"]:
                if item["album"]:
                    all_ids.add(item["album"]["id"])

            self._log("progress", f"Fetching Spotify albums: {len(all_ids)}...")

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return all_ids

    async def _get_all_spotify_followed_artist_ids(self) -> Set[str]:
        """Get ALL followed artist IDs from Spotify."""
        all_ids = set()
        results = self.spotify.current_user_followed_artists()["artists"]

        while True:
            for artist in results["items"]:
                all_ids.add(artist["id"])

            self._log("progress", f"Fetching Spotify artists: {len(all_ids)}...")

            if not results["next"]:
                break
            results = self.spotify.next(results)["artists"]

        return all_ids
