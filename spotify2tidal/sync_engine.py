"""SyncEngine implementation.

This module holds the core engine wiring and item/favorites sync. Larger
playlist/backup implementations are delegated to helper modules to keep files
small and focused.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List, Optional, Set, Tuple

import spotipy
from tqdm import tqdm

from .cache import MatchCache
from .fetchers import SpotifyFetcher
from .library_exporter import LibraryExporter
from .rate_limiter import RateLimiter
from .sync_backup import export_backup as _export_backup
from .sync_backup import export_tidal_library as _export_tidal_library
from .sync_operations import SyncConfig, sync_items, sync_items_batched
from .sync_playlists import (
    sync_all_playlists as _sync_all_playlists,
)
from .sync_playlists import (
    sync_all_playlists_to_spotify as _sync_all_playlists_to_spotify,
)
from .sync_playlists import (
    sync_playlist as _sync_playlist,
)
from .sync_playlists import (
    sync_tidal_playlist_to_spotify as _sync_tidal_playlist_to_spotify,
)

if TYPE_CHECKING:
    import tidalapi

    from .apple_music_client import AppleMusicClient
    from .logging_utils import SyncLogger

logger = logging.getLogger(__name__)


class SyncEngine:
    """Main sync engine for transferring between music platforms."""

    def __init__(
        self,
        spotify: spotipy.Spotify,
        tidal: Optional["tidalapi.Session"] = None,
        apple_music: Optional["AppleMusicClient"] = None,
        max_concurrent: int = 10,
        rate_limit: float = 10,
        library_dir: Optional[str] = "./library",
        logger: Optional["SyncLogger"] = None,
        cache: Optional[MatchCache] = None,
        progress_callback=None,
        item_limit: Optional[int] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.spotify = spotify
        self.tidal = tidal
        self.apple_music = apple_music
        self.cache = cache or MatchCache()
        self.rate_limiter = rate_limiter or RateLimiter(max_concurrent, rate_limit)

        # Tidal components (optional)
        self.searcher = None
        self.tidal_fetcher = None
        if tidal:
            from .fetchers import TidalFetcher
            from .searcher import TidalSearcher

            self.searcher = TidalSearcher(tidal, self.cache, self.rate_limiter)
            self.tidal_fetcher = TidalFetcher(
                tidal, progress_callback=lambda msg: self._log("progress", msg)
            )

        # Apple Music components (optional)
        self.apple_music_searcher = None
        self.apple_music_fetcher = None
        if apple_music:
            from .apple_music_searcher import AppleMusicSearcher
            from .fetchers import AppleMusicFetcher

            self.apple_music_searcher = AppleMusicSearcher(
                apple_music, self.cache, self.rate_limiter
            )
            self.apple_music_fetcher = AppleMusicFetcher(
                apple_music,
                progress_callback=lambda msg: self._log("progress", msg),
            )

        if library_dir is None:
            self.library = LibraryExporter(None, logger=logger)
        elif library_dir:
            self.library = LibraryExporter(library_dir, logger=logger)
        else:
            self.library = None

        self._logger = logger
        self._progress_callback = progress_callback
        self._item_limit = item_limit

        self.spotify_fetcher = SpotifyFetcher(
            spotify, progress_callback=lambda msg: self._log("progress", msg)
        )

    def _log(self, level: str, message: str):
        if self._logger:
            getattr(self._logger, level)(message)
        else:
            print(message)

    def _apply_limit(self, items: list) -> list:
        if self._item_limit and len(items) > self._item_limit:
            return items[: self._item_limit]
        return items

    async def _fetch_with_limit(
        self, fetch_fn: Callable, use_limit_total: bool = False, **kwargs
    ) -> list:
        if self._item_limit:
            if use_limit_total:
                kwargs["limit_total"] = self._item_limit
            else:
                kwargs["limit"] = self._item_limit
        return await fetch_fn(**kwargs)

    async def _fetch_spotify_saved_tracks(self) -> List[dict]:
        return await self._fetch_with_limit(self.spotify_fetcher.get_saved_tracks)

    async def _fetch_spotify_saved_albums(self) -> List[dict]:
        return await self._fetch_with_limit(self.spotify_fetcher.get_saved_albums)

    async def _fetch_spotify_followed_artists(self) -> List[dict]:
        return await self._fetch_with_limit(self.spotify_fetcher.get_followed_artists)

    async def _fetch_spotify_saved_shows(self) -> List[dict]:
        return await self._fetch_with_limit(self.spotify_fetcher.get_saved_shows)

    def _require_tidal(self):
        """Raise if Tidal is not configured."""
        if not self.tidal or not self.tidal_fetcher:
            raise RuntimeError("Tidal session is required for this operation")

    def _require_apple_music(self):
        """Raise if Apple Music is not configured."""
        if not self.apple_music or not self.apple_music_fetcher:
            raise RuntimeError("Apple Music session is required for this operation")

    async def _fetch_tidal_favorite_tracks(self) -> list:
        self._require_tidal()
        return await self._fetch_with_limit(
            self.tidal_fetcher.get_favorite_tracks, use_limit_total=True
        )

    async def _fetch_tidal_favorite_albums(self) -> list:
        self._require_tidal()
        return await self._fetch_with_limit(
            self.tidal_fetcher.get_favorite_albums, use_limit_total=True
        )

    async def _fetch_tidal_favorite_artists(self) -> list:
        self._require_tidal()
        return await self._fetch_with_limit(
            self.tidal_fetcher.get_favorite_artists, use_limit_total=True
        )

    def _report_progress(self, **kwargs):
        if self._progress_callback:
            self._progress_callback(**kwargs)

    def _progress_iter(self, iterable, desc: str, phase: str = "searching"):
        items = list(iterable)
        total = len(items)

        self._report_progress(event="phase", phase=phase)
        self._report_progress(event="total", total=total)
        self._report_progress(event="update", current=0, total=total, phase=phase)

        for i, item in enumerate(tqdm(items, desc=desc)):
            yield item
            self._report_progress(event="update", current=i + 1, total=total, phase=phase)

    # ---------------------------------------------------------------------
    # Forward sync (Spotify -> Tidal)
    # ---------------------------------------------------------------------

    async def sync_favorites(self) -> Tuple[int, int]:
        self._require_tidal()
        return await sync_items(
            SyncConfig(
                item_type="track",
                fetch_source=self._fetch_spotify_saved_tracks,
                fetch_existing_ids=self.tidal_fetcher.get_favorite_track_ids,
                search_item=self.searcher.search_track,
                get_source_id=lambda item: item.get("id"),
                get_cache_match=self.cache.get_track_match,
                add_item=self.tidal.user.favorites.add_track,
                add_to_library=self.library.add_tracks if self.library else None,
                add_not_found=self.library.add_not_found_track if self.library else None,
                progress_desc="Syncing favorite tracks",
            ),
            self,
        )

    async def sync_albums(self) -> Tuple[int, int]:
        self._require_tidal()
        return await sync_items(
            SyncConfig(
                item_type="album",
                fetch_source=self._fetch_spotify_saved_albums,
                fetch_existing_ids=self.tidal_fetcher.get_favorite_album_ids,
                search_item=lambda item: self.searcher.search_album(item.get("album", {})),
                get_source_id=lambda item: item.get("album", {}).get("id"),
                get_cache_match=self.cache.get_album_match,
                add_item=self.tidal.user.favorites.add_album,
                add_to_library=self.library.add_albums if self.library else None,
                add_not_found=self.library.add_not_found_album if self.library else None,
                progress_desc="Syncing albums",
            ),
            self,
        )

    async def sync_artists(self) -> Tuple[int, int]:
        self._require_tidal()
        return await sync_items(
            SyncConfig(
                item_type="artist",
                fetch_source=self._fetch_spotify_followed_artists,
                fetch_existing_ids=self.tidal_fetcher.get_favorite_artist_ids,
                search_item=self.searcher.search_artist,
                get_source_id=lambda item: item.get("id"),
                get_cache_match=self.cache.get_artist_match,
                add_item=self.tidal.user.favorites.add_artist,
                add_to_library=self.library.add_artists if self.library else None,
                add_not_found=self.library.add_not_found_artist if self.library else None,
                progress_desc="Syncing artists",
            ),
            self,
        )

    async def sync_playlist(
        self, spotify_playlist_id: str, tidal_playlist_id: Optional[str] = None
    ) -> Tuple[int, int]:
        return await _sync_playlist(self, spotify_playlist_id, tidal_playlist_id)

    async def sync_all_playlists(self) -> dict:
        return await _sync_all_playlists(self)

    async def export_podcasts(self) -> int:
        self._report_progress(event="phase", phase="fetching")
        podcasts = await self._fetch_spotify_saved_shows()
        logger.info(f"Found {len(podcasts)} saved podcasts/shows on Spotify")
        if podcasts and self.library:
            self.library.add_podcasts(podcasts)
        return len(podcasts)

    def export_library(self) -> dict:
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

        logger.info("No library data to export")
        return {"files": {}, "stats": stats}

    async def export_tidal_library(self) -> dict:
        return await _export_tidal_library(self)

    async def export_backup(self, categories: Optional[List[str]] = None) -> dict:
        return await _export_backup(self, categories=categories)

    # ---------------------------------------------------------------------
    # Reverse sync (Tidal -> Spotify)
    # ---------------------------------------------------------------------

    async def sync_tidal_playlist_to_spotify(self, tidal_playlist) -> Tuple[int, int]:
        return await _sync_tidal_playlist_to_spotify(self, tidal_playlist)

    async def sync_all_playlists_to_spotify(self) -> dict:
        return await _sync_all_playlists_to_spotify(self)

    async def sync_favorites_to_spotify(self) -> Tuple[int, int]:
        from .spotify_searcher import SpotifySearcher

        searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        return await sync_items_batched(
            SyncConfig(
                item_type="track",
                fetch_source=self._fetch_tidal_favorite_tracks,
                fetch_existing_ids=self.spotify_fetcher.get_saved_track_ids,
                search_item=searcher.search_track,
                get_source_id=lambda item: item.id,
                get_cache_match=self.cache.get_spotify_track_match,
                add_item=lambda x: None,
                add_to_library=self.library.add_tidal_source_tracks if self.library else None,
                add_not_found=self.library.add_not_found_tidal_track if self.library else None,
                progress_desc="Syncing favorite tracks to Spotify",
                reverse_order=False,
            ),
            self,
            batch_add=lambda items: self.spotify.current_user_saved_tracks_add(tracks=items),
        )

    async def sync_albums_to_spotify(self) -> Tuple[int, int]:
        from .spotify_searcher import SpotifySearcher

        searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        return await sync_items_batched(
            SyncConfig(
                item_type="album",
                fetch_source=self._fetch_tidal_favorite_albums,
                fetch_existing_ids=self.spotify_fetcher.get_saved_album_ids,
                search_item=searcher.search_album,
                get_source_id=lambda item: item.id,
                get_cache_match=self.cache.get_spotify_album_match,
                add_item=lambda x: None,
                add_to_library=self.library.add_tidal_source_albums if self.library else None,
                add_not_found=self.library.add_not_found_tidal_album if self.library else None,
                progress_desc="Syncing favorite albums to Spotify",
                reverse_order=False,
            ),
            self,
            batch_add=lambda items: self.spotify.current_user_saved_albums_add(albums=items),
        )

    async def sync_artists_to_spotify(self) -> Tuple[int, int]:
        from .spotify_searcher import SpotifySearcher

        searcher = SpotifySearcher(self.spotify, self.cache, self.rate_limiter)

        return await sync_items_batched(
            SyncConfig(
                item_type="artist",
                fetch_source=self._fetch_tidal_favorite_artists,
                fetch_existing_ids=self.spotify_fetcher.get_followed_artist_ids,
                search_item=searcher.search_artist,
                get_source_id=lambda item: item.id,
                get_cache_match=self.cache.get_spotify_artist_match,
                add_item=lambda x: None,
                add_to_library=self.library.add_tidal_source_artists if self.library else None,
                add_not_found=self.library.add_not_found_tidal_artist if self.library else None,
                progress_desc="Syncing favorite artists to Spotify",
                reverse_order=False,
            ),
            self,
            batch_add=lambda items: self.spotify.user_follow_artists(ids=items),
        )

    # ---------------------------------------------------------------------
    # Utility methods used by CLI
    # ---------------------------------------------------------------------

    async def _get_all_tidal_favorite_track_ids(self) -> Set[int]:
        return await self.tidal_fetcher.get_favorite_track_ids()

    async def _get_all_tidal_favorite_album_ids(self) -> Set[int]:
        return await self.tidal_fetcher.get_favorite_album_ids()

    async def _get_all_tidal_favorite_artist_ids(self) -> Set[int]:
        return await self.tidal_fetcher.get_favorite_artist_ids()

    async def _get_all_spotify_saved_track_ids(self) -> Set[str]:
        return await self.spotify_fetcher.get_saved_track_ids()

    async def _get_all_spotify_saved_album_ids(self) -> Set[str]:
        return await self.spotify_fetcher.get_saved_album_ids()

    async def _get_all_spotify_followed_artist_ids(self) -> Set[str]:
        return await self.spotify_fetcher.get_followed_artist_ids()

    # ---------------------------------------------------------------------
    # Apple Music sync (Spotify -> Apple Music)
    # ---------------------------------------------------------------------

    async def sync_favorites_to_apple_music(self) -> Tuple[int, int]:
        self._require_apple_music()

        return await sync_items(
            SyncConfig(
                item_type="track",
                fetch_source=self._fetch_spotify_saved_tracks,
                fetch_existing_ids=self.apple_music_fetcher.get_library_song_ids,
                search_item=self.apple_music_searcher.search_track,
                get_source_id=lambda item: item.get("id"),
                get_cache_match=self.cache.get_apple_track_match,
                add_item=lambda apple_id: self.apple_music.add_songs_to_library([apple_id]),
                add_to_library=self.library.add_tracks if self.library else None,
                add_not_found=(self.library.add_not_found_track if self.library else None),
                progress_desc="Syncing favorite tracks to Apple Music",
            ),
            self,
        )

    async def sync_albums_to_apple_music(self) -> Tuple[int, int]:
        self._require_apple_music()

        return await sync_items(
            SyncConfig(
                item_type="album",
                fetch_source=self._fetch_spotify_saved_albums,
                fetch_existing_ids=self.apple_music_fetcher.get_library_album_ids,
                search_item=lambda item: self.apple_music_searcher.search_album(
                    item.get("album", {})
                ),
                get_source_id=lambda item: item.get("album", {}).get("id"),
                get_cache_match=self.cache.get_apple_album_match,
                add_item=lambda apple_id: self.apple_music.add_albums_to_library([apple_id]),
                add_to_library=self.library.add_albums if self.library else None,
                add_not_found=(self.library.add_not_found_album if self.library else None),
                progress_desc="Syncing albums to Apple Music",
            ),
            self,
        )

    async def sync_playlist_to_apple_music(self, spotify_playlist_id: str) -> Tuple[int, int]:
        """Sync a single Spotify playlist to Apple Music."""
        self._require_apple_music()

        # Get playlist info from Spotify
        playlist_data = self.spotify.playlist(spotify_playlist_id)
        playlist_name = playlist_data.get("name", "Untitled")

        self._log("info", f"Syncing playlist: {playlist_name}")

        # Get or create Apple Music playlist
        am_playlist_id = self.apple_music.get_or_create_playlist(playlist_name)
        if not am_playlist_id:
            self._log("error", f"Failed to create Apple Music playlist: {playlist_name}")
            return (0, 0)

        # Get existing track IDs to avoid duplicates
        existing_ids = self.apple_music.get_library_playlist_track_ids(am_playlist_id)

        # Fetch Spotify playlist tracks
        tracks = await self.spotify_fetcher.get_playlist_tracks(spotify_playlist_id)
        if self._item_limit:
            tracks = tracks[: self._item_limit]

        self._log("info", f"Found {len(tracks)} tracks in Spotify playlist")

        # Search and collect Apple Music IDs (preserving order)
        apple_ids_to_add = []
        not_found_count = 0

        for track in self._progress_iter(tracks, f"Matching: {playlist_name}"):
            spotify_track = track.get("track", track)
            if not spotify_track or not spotify_track.get("id"):
                continue

            # Search for the track on Apple Music
            apple_id = await self.apple_music_searcher.search_track(spotify_track)
            if apple_id:
                if apple_id not in existing_ids:
                    apple_ids_to_add.append(apple_id)
            else:
                not_found_count += 1
                if self.library:
                    self.library.add_not_found_track(spotify_track)

        # Add tracks in order (batches of 100)
        if apple_ids_to_add:
            self.apple_music.add_tracks_to_playlist(am_playlist_id, apple_ids_to_add)
            self._log(
                "info",
                f"Added {len(apple_ids_to_add)} tracks to Apple Music playlist "
                f"'{playlist_name}'",
            )

        return (len(apple_ids_to_add), not_found_count)

    async def sync_all_playlists_to_apple_music(self) -> dict:
        """Sync all Spotify playlists to Apple Music."""
        self._require_apple_music()

        playlists = await self.spotify_fetcher.get_playlists()
        self._log("info", f"Found {len(playlists)} Spotify playlists")

        results = {}
        for playlist in playlists:
            playlist_id = playlist.get("id")
            playlist_name = playlist.get("name", "Untitled")

            try:
                added, not_found = await self.sync_playlist_to_apple_music(playlist_id)
                results[playlist_name] = {
                    "added": added,
                    "not_found": not_found,
                }
            except Exception as e:
                self._log("error", f"Failed to sync playlist '{playlist_name}': {e}")
                results[playlist_name] = {"error": str(e)}

        return results
