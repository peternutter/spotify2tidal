"""
Main sync engine for transferring from Spotify to Tidal.
"""

import logging
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import spotipy
import tidalapi
from tqdm import tqdm

from .cache import MatchCache
from .fetchers import SpotifyFetcher, TidalFetcher
from .library import LibraryExporter
from .matching import TrackMatcher, normalize, simplify
from .rate_limiter import RateLimiter
from .searcher import TidalSearcher
from .sync_operations import SyncConfig, sync_items, sync_items_batched

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
        item_limit: Optional[int] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.spotify = spotify
        self.tidal = tidal
        self.cache = cache or MatchCache()
        # Use provided rate_limiter or create new one
        self.rate_limiter = rate_limiter or RateLimiter(max_concurrent, rate_limit)
        self.searcher = TidalSearcher(tidal, self.cache, self.rate_limiter)
        self.library = LibraryExporter(library_dir) if library_dir else None
        self._logger = logger
        self._progress_callback = progress_callback
        self._item_limit = item_limit

        # Initialize fetchers with progress callback
        def log_progress(msg: str):
            self._log("progress", msg)

        self.spotify_fetcher = SpotifyFetcher(spotify, progress_callback=log_progress)
        self.tidal_fetcher = TidalFetcher(tidal, progress_callback=log_progress)

    def _log(self, level: str, message: str):
        """Log a message using the provided logger or fallback to print."""
        if self._logger:
            getattr(self._logger, level)(message)
        else:
            # Fallback to print for backwards compatibility
            print(message)

    def _apply_limit(self, items: list) -> list:
        """Apply item limit if configured (for debug mode)."""
        if self._item_limit and len(items) > self._item_limit:
            return items[: self._item_limit]
        return items

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
            if self.library:
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
            if self.library:
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
        return await sync_items(
            SyncConfig(
                item_type="track",
                fetch_source=self.spotify_fetcher.get_saved_tracks,
                fetch_existing_ids=self.tidal_fetcher.get_favorite_track_ids,
                search_item=self.searcher.search_track,
                get_source_id=lambda item: item.get("id"),
                get_cache_match=self.cache.get_track_match,
                add_item=self.tidal.user.favorites.add_track,
                add_to_library=self.library.add_tracks if self.library else None,
                add_not_found=self.library.add_not_found_track
                if self.library
                else None,
                progress_desc="Syncing favorite tracks",
            ),
            self,
        )

    async def sync_albums(self) -> Tuple[int, int]:
        """
        Sync saved albums from Spotify to Tidal.

        Albums are added oldest-first so they appear at the bottom in Tidal,
        preserving the chronological order from Spotify.
        """
        return await sync_items(
            SyncConfig(
                item_type="album",
                fetch_source=self.spotify_fetcher.get_saved_albums,
                fetch_existing_ids=self.tidal_fetcher.get_favorite_album_ids,
                search_item=lambda item: self.searcher.search_album(
                    item.get("album", {})
                ),
                get_source_id=lambda item: item.get("album", {}).get("id"),
                get_cache_match=self.cache.get_album_match,
                add_item=self.tidal.user.favorites.add_album,
                add_to_library=self.library.add_albums if self.library else None,
                add_not_found=self.library.add_not_found_album
                if self.library
                else None,
                progress_desc="Syncing albums",
            ),
            self,
        )

    async def sync_artists(self) -> Tuple[int, int]:
        """
        Sync followed artists from Spotify to Tidal.

        Artists are added oldest-first so they appear at the bottom in Tidal,
        preserving the chronological order from Spotify.
        """
        return await sync_items(
            SyncConfig(
                item_type="artist",
                fetch_source=self.spotify_fetcher.get_followed_artists,
                fetch_existing_ids=self.tidal_fetcher.get_favorite_artist_ids,
                search_item=self.searcher.search_artist,
                get_source_id=lambda item: item.get("id"),
                get_cache_match=self.cache.get_artist_match,
                add_item=self.tidal.user.favorites.add_artist,
                add_to_library=self.library.add_artists if self.library else None,
                add_not_found=self.library.add_not_found_artist
                if self.library
                else None,
                progress_desc="Syncing artists",
            ),
            self,
        )

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

        if podcasts and self.library:
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
        return await self.spotify_fetcher.get_playlist_tracks(playlist_id)

    async def _get_spotify_saved_tracks(self) -> List[dict]:
        """Get all saved/liked tracks from Spotify."""
        return await self.spotify_fetcher.get_saved_tracks()

    async def _get_spotify_saved_albums(self) -> List[dict]:
        """Get all saved albums from Spotify."""
        return await self.spotify_fetcher.get_saved_albums()

    async def _get_spotify_followed_artists(self) -> List[dict]:
        """Get all followed artists from Spotify."""
        return await self.spotify_fetcher.get_followed_artists()

    async def _get_all_tidal_favorite_track_ids(self) -> Set[int]:
        """Get ALL favorite track IDs from Tidal with proper pagination."""
        return await self.tidal_fetcher.get_favorite_track_ids()

    async def _get_all_tidal_favorite_album_ids(self) -> Set[int]:
        """Get ALL favorite album IDs from Tidal with proper pagination."""
        return await self.tidal_fetcher.get_favorite_album_ids()

    async def _get_all_tidal_favorite_artist_ids(self) -> Set[int]:
        """Get ALL favorite artist IDs from Tidal with proper pagination."""
        return await self.tidal_fetcher.get_favorite_artist_ids()

    async def _get_all_tidal_playlist_track_ids(
        self, playlist: tidalapi.Playlist
    ) -> Set[int]:
        """Get ALL track IDs from a Tidal playlist with proper pagination."""
        return await self.tidal_fetcher.get_playlist_track_ids(playlist)

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
        if not self.library:
            return {"files": {}, "stats": {}}

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
        if not self.library:
            return {}

        from .library import (
            export_tidal_albums,
            export_tidal_artists,
            export_tidal_tracks,
        )

        results = {}

        # Fetch and export Tidal tracks using fetcher
        self._log("progress", "Fetching Tidal favorite tracks...")
        tracks = await self.tidal_fetcher.get_favorite_tracks()
        if tracks:
            results["tidal_tracks"] = export_tidal_tracks(
                tracks, self.library.export_dir
            )
            logger.info(f"Exported {len(tracks)} Tidal tracks")

        # Fetch and export Tidal albums using fetcher
        self._log("progress", "Fetching Tidal favorite albums...")
        albums = await self.tidal_fetcher.get_favorite_albums()
        if albums:
            results["tidal_albums"] = export_tidal_albums(
                albums, self.library.export_dir
            )
            logger.info(f"Exported {len(albums)} Tidal albums")

        # Fetch and export Tidal artists using fetcher
        self._log("progress", "Fetching Tidal favorite artists...")
        artists = await self.tidal_fetcher.get_favorite_artists()
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

        searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        return await sync_items_batched(
            SyncConfig(
                item_type="track",
                fetch_source=self.tidal_fetcher.get_favorite_tracks,
                fetch_existing_ids=self.spotify_fetcher.get_saved_track_ids,
                search_item=searcher.search_track,
                get_source_id=lambda item: item.id,
                get_cache_match=self.cache.get_spotify_track_match,
                add_item=lambda x: None,  # Handled by batch_add
                progress_desc="Syncing favorite tracks to Spotify",
                reverse_order=False,
            ),
            self,
            batch_add=lambda items: self.spotify.current_user_saved_tracks_add(
                tracks=items
            ),
        )

    async def sync_albums_to_spotify(self) -> Tuple[int, int]:
        """
        Sync favorite albums from Tidal to Spotify library.

        Returns: (albums_added, albums_not_found)
        """
        from .spotify_searcher import SpotifySearcher

        searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        return await sync_items_batched(
            SyncConfig(
                item_type="album",
                fetch_source=self.tidal_fetcher.get_favorite_albums,
                fetch_existing_ids=self.spotify_fetcher.get_saved_album_ids,
                search_item=searcher.search_album,
                get_source_id=lambda item: item.id,
                get_cache_match=self.cache.get_spotify_album_match,
                add_item=lambda x: None,  # Handled by batch_add
                progress_desc="Syncing favorite albums to Spotify",
                reverse_order=False,
            ),
            self,
            batch_add=lambda items: self.spotify.current_user_saved_albums_add(
                albums=items
            ),
        )

    async def sync_artists_to_spotify(self) -> Tuple[int, int]:
        """
        Sync followed artists from Tidal to Spotify.

        Returns: (artists_added, artists_not_found)
        """
        from .spotify_searcher import SpotifySearcher

        searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        return await sync_items_batched(
            SyncConfig(
                item_type="artist",
                fetch_source=self.tidal_fetcher.get_favorite_artists,
                fetch_existing_ids=self.spotify_fetcher.get_followed_artist_ids,
                search_item=searcher.search_artist,
                get_source_id=lambda item: item.id,
                get_cache_match=self.cache.get_spotify_artist_match,
                add_item=lambda x: None,  # Handled by batch_add
                progress_desc="Syncing followed artists to Spotify",
                reverse_order=False,
            ),
            self,
            batch_add=lambda items: self.spotify.user_follow_artists(ids=items),
        )
