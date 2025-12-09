"""
Advanced sync engine with async support, smart matching, and caching.
"""

import asyncio
import logging
import unicodedata
from difflib import SequenceMatcher
from typing import List, Optional, Set, Tuple

import spotipy
import tidalapi
from tqdm import tqdm
from tqdm.asyncio import tqdm as atqdm

from .cache import MatchCache
from .library import LibraryExporter

logger = logging.getLogger(__name__)


def normalize(s: str) -> str:
    """Normalize unicode characters to ASCII."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def simplify(text: str) -> str:
    """Simplify track/album name by removing version info in brackets/parentheses."""
    return text.split("-")[0].strip().split("(")[0].strip().split("[")[0].strip()


class TrackMatcher:
    """Smart track matching with multiple strategies."""

    @staticmethod
    def isrc_match(tidal_track: tidalapi.Track, spotify_track: dict) -> bool:
        """Match by ISRC (International Standard Recording Code) - most reliable."""
        if "isrc" in spotify_track.get("external_ids", {}):
            return tidal_track.isrc == spotify_track["external_ids"]["isrc"]
        return False

    @staticmethod
    def duration_match(
        tidal_track: tidalapi.Track, spotify_track: dict, tolerance: int = 2
    ) -> bool:
        """Check if durations match within tolerance (seconds)."""
        tidal_duration = tidal_track.duration
        spotify_duration = spotify_track.get("duration_ms", 0) / 1000
        return abs(tidal_duration - spotify_duration) < tolerance

    @staticmethod
    def name_match(tidal_track: tidalapi.Track, spotify_track: dict) -> bool:
        """Check if track names match, handling various edge cases."""

        def has_pattern(name: str, pattern: str) -> bool:
            return pattern in name.lower()

        # Exclusion rules - if one has it and the other doesn't, it's not a match
        patterns = [
            "instrumental",
            "acapella",
            "remix",
            "live",
            "acoustic",
            "radio edit",
        ]
        tidal_name = tidal_track.name.lower()
        tidal_version = (tidal_track.version or "").lower()
        spotify_name = spotify_track["name"].lower()

        for pattern in patterns:
            tidal_has = has_pattern(tidal_name, pattern) or has_pattern(
                tidal_version, pattern
            )
            spotify_has = has_pattern(spotify_name, pattern)
            if tidal_has != spotify_has:
                return False

        # Simplified name comparison
        simple_spotify = simplify(spotify_name).split("feat.")[0].strip()
        return simple_spotify in tidal_name or normalize(simple_spotify) in normalize(
            tidal_name
        )

    @staticmethod
    def artist_match(tidal_item, spotify_item: dict) -> bool:
        """Check if at least one artist matches between Tidal and Spotify."""

        def split_artists(name: str) -> Set[str]:
            parts = []
            for sep in ["&", ",", "/"]:
                if sep in name:
                    parts.extend(name.split(sep))
                    break
            else:
                parts = [name]
            return {simplify(p.strip().lower()) for p in parts}

        def get_tidal_artists(item, do_normalize: bool = False) -> Set[str]:
            result = set()
            for artist in item.artists:
                name = normalize(artist.name) if do_normalize else artist.name
                result.update(split_artists(name))
            return result

        def get_spotify_artists(item: dict, do_normalize: bool = False) -> Set[str]:
            result = set()
            for artist in item.get("artists", []):
                name = normalize(artist["name"]) if do_normalize else artist["name"]
                result.update(split_artists(name))
            return result

        # Try un-normalized first, then normalized
        if get_tidal_artists(tidal_item) & get_spotify_artists(spotify_item):
            return True
        return bool(
            get_tidal_artists(tidal_item, True)
            & get_spotify_artists(spotify_item, True)
        )

    @classmethod
    def match(cls, tidal_track: tidalapi.Track, spotify_track: dict) -> bool:
        """Full match check using all strategies."""
        if not spotify_track.get("id"):
            return False

        # ISRC is the most reliable - if it matches, we're done
        if cls.isrc_match(tidal_track, spotify_track):
            return True

        # Otherwise, use combination of duration, name, and artist
        return (
            cls.duration_match(tidal_track, spotify_track)
            and cls.name_match(tidal_track, spotify_track)
            and cls.artist_match(tidal_track, spotify_track)
        )

    @classmethod
    def album_match(
        cls, tidal_album: tidalapi.Album, spotify_album: dict, threshold: float = 0.6
    ) -> bool:
        """Check if albums match by name similarity and artist."""
        name_similarity = SequenceMatcher(
            None,
            simplify(spotify_album["name"]).lower(),
            simplify(tidal_album.name).lower(),
        ).ratio()
        return name_similarity >= threshold and cls.artist_match(
            tidal_album, spotify_album
        )


class RateLimiter:
    """Async rate limiter using leaky bucket algorithm."""

    def __init__(self, max_concurrent: int = 10, rate_per_second: float = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate = rate_per_second
        self._task: Optional[asyncio.Task] = None

    async def _leak(self):
        """Periodically release from semaphore."""
        sleep_time = 1.0 / self.rate
        while True:
            await asyncio.sleep(sleep_time)
            try:
                self.semaphore.release()
            except ValueError:
                pass  # Already at max

    def start(self):
        """Start the rate limiter."""
        if not self._task:
            self._task = asyncio.create_task(self._leak())

    def stop(self):
        """Stop the rate limiter."""
        if self._task:
            self._task.cancel()
            self._task = None

    async def acquire(self):
        """Acquire a slot."""
        await self.semaphore.acquire()


class TidalSearcher:
    """Async Tidal search with smart matching."""

    def __init__(
        self, session: tidalapi.Session, cache: MatchCache, rate_limiter: RateLimiter
    ):
        self.session = session
        self.cache = cache
        self.rate_limiter = rate_limiter

    async def search_track(self, spotify_track: dict) -> Optional[int]:
        """Search for a Spotify track on Tidal, return Tidal track ID if found."""
        spotify_id = spotify_track.get("id")
        if not spotify_id:
            return None

        # Check cache first
        cached = self.cache.get_track_match(spotify_id)
        if cached is not None:
            return cached if cached > 0 else None

        # Check if we've failed before
        if self.cache.has_recent_failure(spotify_id):
            return None

        # Try album search first (more accurate)
        result = await self._search_by_album(spotify_track)
        if result:
            self.cache.cache_track_match(spotify_id, result)
            return result

        # Fall back to direct track search
        result = await self._search_by_track(spotify_track)
        if result:
            self.cache.cache_track_match(spotify_id, result)
            return result

        # Cache the failure
        self.cache.cache_failure(spotify_id)
        return None

    async def _search_by_album(self, spotify_track: dict) -> Optional[int]:
        """Search by album and track number."""
        album = spotify_track.get("album", {})
        artists = album.get("artists", [])

        if not album.get("name") or not artists:
            return None

        query = f"{simplify(album['name'])} {simplify(artists[0]['name'])}"

        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, query, models=[tidalapi.album.Album]
            )

            for tidal_album in results.get("albums", []):
                if not TrackMatcher.album_match(tidal_album, album):
                    continue

                track_num = spotify_track.get("track_number", 0)
                if tidal_album.num_tracks < track_num:
                    continue

                tracks = await asyncio.to_thread(tidal_album.tracks)
                if len(tracks) >= track_num:
                    track = tracks[track_num - 1]
                    if track.available and TrackMatcher.match(track, spotify_track):
                        return track.id
        except Exception as e:
            logger.warning(f"Album search failed: {e}")

        return None

    async def _search_by_track(self, spotify_track: dict) -> Optional[int]:
        """Direct track search."""
        artists = spotify_track.get("artists", [])
        if not artists:
            return None

        query = f"{simplify(spotify_track['name'])} {simplify(artists[0]['name'])}"

        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, query, models=[tidalapi.media.Track]
            )

            for track in results.get("tracks", []):
                if track.available and TrackMatcher.match(track, spotify_track):
                    return track.id
        except Exception as e:
            logger.warning(f"Track search failed: {e}")

        return None

    async def search_album(self, spotify_album: dict) -> Optional[int]:
        """Search for a Spotify album on Tidal."""
        artists = spotify_album.get("artists", [])
        if not artists:
            return None

        query = f"{simplify(spotify_album['name'])} {simplify(artists[0]['name'])}"

        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, query, models=[tidalapi.album.Album]
            )

            for album in results.get("albums", []):
                if TrackMatcher.album_match(album, spotify_album):
                    return album.id
        except Exception as e:
            logger.warning(f"Album search failed: {e}")

        return None

    async def search_artist(self, name: str) -> Optional[int]:
        """Search for an artist on Tidal."""
        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, name, models=[tidalapi.artist.Artist]
            )

            for artist in results.get("artists", []):
                if artist.name.lower() == name.lower():
                    return artist.id
                if normalize(artist.name.lower()) == normalize(name.lower()):
                    return artist.id
        except Exception as e:
            logger.warning(f"Artist search failed: {e}")

        return None


class SyncEngine:
    """Main sync engine for transferring from Spotify to Tidal."""

    def __init__(
        self,
        spotify: spotipy.Spotify,
        tidal: tidalapi.Session,
        max_concurrent: int = 10,
        rate_limit: float = 10,
        library_dir: str = "./library",
    ):
        self.spotify = spotify
        self.tidal = tidal
        self.cache = MatchCache()
        self.rate_limiter = RateLimiter(max_concurrent, rate_limit)
        self.searcher = TidalSearcher(tidal, self.cache, self.rate_limiter)
        self.library = LibraryExporter(library_dir)

    async def sync_playlist(
        self, spotify_playlist_id: str, tidal_playlist_id: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Sync a Spotify playlist to Tidal.

        Returns: (tracks_added, tracks_not_found)
        """
        self.rate_limiter.start()
        try:
            # Get Spotify tracks
            spotify_tracks = await self._get_spotify_playlist_tracks(
                spotify_playlist_id
            )
            playlist_name = self.spotify.playlist(spotify_playlist_id)["name"]
            logger.info(
                f"Found {len(spotify_tracks)} tracks in Spotify playlist '{playlist_name}'"
            )

            if not spotify_tracks:
                return 0, 0

            # Get or create Tidal playlist
            if tidal_playlist_id:
                tidal_playlist = self.tidal.playlist(tidal_playlist_id)
            else:
                # Find existing or create new
                tidal_playlist = await self._get_or_create_tidal_playlist(playlist_name)

            # Get existing Tidal tracks
            existing_tidal_ids = set()
            if tidal_playlist.num_tracks > 0:
                existing_tracks = tidal_playlist.tracks()
                existing_tidal_ids = {t.id for t in existing_tracks}

            # Save all tracks to library export
            self.library.add_tracks(spotify_tracks)

            # Search for tracks on Tidal
            tidal_track_ids = []
            not_found = []
            not_found_tracks = []

            tasks = [self.searcher.search_track(t) for t in spotify_tracks]
            results = await atqdm.gather(*tasks, desc="Searching Tidal for tracks")

            for spotify_track, tidal_id in zip(spotify_tracks, results):
                if tidal_id:
                    tidal_track_ids.append(tidal_id)
                else:
                    not_found.append(
                        f"{spotify_track['artists'][0]['name']} - {spotify_track['name']}"
                    )
                    not_found_tracks.append(spotify_track)

            # Record not-found tracks for export
            for track in not_found_tracks:
                self.library.add_not_found_track(track)

            # Add only new tracks
            new_ids = [tid for tid in tidal_track_ids if tid not in existing_tidal_ids]

            if new_ids:
                # Add in chunks
                chunk_size = 50
                for i in tqdm(
                    range(0, len(new_ids), chunk_size), desc="Adding tracks to Tidal"
                ):
                    chunk = new_ids[i : i + chunk_size]
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
            # Get Spotify saved tracks (returned newest-first)
            spotify_tracks = await self._get_spotify_saved_tracks()
            logger.info(f"Found {len(spotify_tracks)} saved tracks on Spotify")

            if not spotify_tracks:
                return 0, 0

            # Reverse to add oldest first (so they end up at bottom in Tidal)
            spotify_tracks = list(reversed(spotify_tracks))

            # Get existing Tidal favorites
            existing_favorites = self.tidal.user.favorites.tracks()
            existing_ids = {t.id for t in existing_favorites}

            # Search and add
            added = 0
            not_found = 0

            tasks = [self.searcher.search_track(t) for t in spotify_tracks]
            results = await atqdm.gather(*tasks, desc="Searching Tidal for favorites")

            # Save all tracks to library export
            self.library.add_tracks(spotify_tracks)

            # Build list of tracks to add (filter out already existing and not found)
            tracks_to_add = []
            not_found_list = []
            for spotify_track, tidal_id in zip(spotify_tracks, results):
                if tidal_id and tidal_id not in existing_ids:
                    tracks_to_add.append(tidal_id)
                elif not tidal_id:
                    not_found += 1
                    not_found_list.append(spotify_track)

            # Record not-found tracks for export
            for track in not_found_list:
                self.library.add_not_found_track(track)

            # Add tracks with progress bar
            for tidal_id in tqdm(tracks_to_add, desc="Adding to Tidal favorites"):
                try:
                    self.tidal.user.favorites.add_track(tidal_id)
                    added += 1
                except Exception as e:
                    logger.warning(f"Failed to add track: {e}")

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
            # Get Spotify saved albums (returned newest-first)
            spotify_albums = await self._get_spotify_saved_albums()
            logger.info(f"Found {len(spotify_albums)} saved albums on Spotify")

            # Reverse to add oldest first (so they end up at bottom in Tidal)
            spotify_albums = list(reversed(spotify_albums))

            # Save all albums to library export
            self.library.add_albums(spotify_albums)

            added = 0
            not_found = 0

            for album in tqdm(spotify_albums, desc="Syncing albums"):
                tidal_id = await self.searcher.search_album(album["album"])
                if tidal_id:
                    try:
                        self.tidal.user.favorites.add_album(tidal_id)
                        added += 1
                    except Exception as e:
                        logger.warning(f"Failed to add album: {e}")
                else:
                    not_found += 1
                    self.library.add_not_found_album(album)
                    logger.warning(
                        f"Album not found: {album['album']['artists'][0]['name']} - {album['album']['name']}"
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
            # Get Spotify followed artists (returned in an order we'll reverse)
            spotify_artists = await self._get_spotify_followed_artists()
            logger.info(f"Found {len(spotify_artists)} followed artists on Spotify")

            # Reverse to add oldest first (so they end up at bottom in Tidal)
            spotify_artists = list(reversed(spotify_artists))

            # Save all artists to library export
            self.library.add_artists(spotify_artists)

            added = 0
            not_found = 0

            for artist in tqdm(spotify_artists, desc="Syncing artists"):
                tidal_id = await self.searcher.search_artist(artist["name"])
                if tidal_id:
                    try:
                        self.tidal.user.favorites.add_artist(tidal_id)
                        added += 1
                    except Exception as e:
                        logger.warning(f"Failed to add artist: {e}")
                else:
                    not_found += 1
                    self.library.add_not_found_artist(artist)
                    logger.warning(f"Artist not found: {artist['name']}")

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

            print(f"\rFetching saved tracks from Spotify: {len(tracks)} tracks...", end="", flush=True)
            
            if not results["next"]:
                break
            results = self.spotify.next(results)
            page += 1

        print()  # New line after progress
        return tracks

    async def _get_spotify_saved_albums(self) -> List[dict]:
        """Get all saved albums from Spotify."""
        albums = []
        results = self.spotify.current_user_saved_albums()

        while True:
            albums.extend(results["items"])
            print(f"\rFetching saved albums from Spotify: {len(albums)} albums...", end="", flush=True)
            
            if not results["next"]:
                break
            results = self.spotify.next(results)

        print()  # New line after progress
        return albums

    async def _get_spotify_followed_artists(self) -> List[dict]:
        """Get all followed artists from Spotify."""
        artists = []
        results = self.spotify.current_user_followed_artists()["artists"]

        while True:
            artists.extend(results["items"])
            print(f"\rFetching followed artists from Spotify: {len(artists)} artists...", end="", flush=True)
            
            if not results["next"]:
                break
            results = self.spotify.next(results)["artists"]

        print()  # New line after progress
        return artists

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

