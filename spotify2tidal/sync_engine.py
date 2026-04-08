"""SyncEngine implementation.

This module holds the core engine wiring and item/favorites sync. Larger
playlist/backup implementations are delegated to helper modules to keep files
small and focused.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Set, Tuple

import spotipy
from tqdm import tqdm

from .cache import MatchCache
from .fetchers import SpotifyFetcher
from .library_exporter import LibraryExporter
from .matching import normalize, simplify
from .rate_limiter import RateLimiter
from .retry_utils import retry_async_call
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
        apple_music_fallback: Optional["AppleMusicClient"] = None,
        max_concurrent: int = 10,
        rate_limit: float = 10,
        library_dir: Optional[str] = "./library",
        logger: Optional["SyncLogger"] = None,
        cache: Optional[MatchCache] = None,
        progress_callback=None,
        item_limit: Optional[int] = None,
        rate_limiter: Optional[RateLimiter] = None,
        skip_existing_check: bool = False,
    ):
        self.spotify = spotify
        self.tidal = tidal
        self.apple_music = apple_music
        self.skip_existing_check = skip_existing_check
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
                apple_music,
                self.cache,
                self.rate_limiter,
                fallback_client=apple_music_fallback,
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

    @staticmethod
    def _normalize_apple_text(value: str) -> str:
        return normalize(simplify(value or "")).lower().strip()

    def _spotify_track_apple_key(self, track: dict) -> Optional[tuple[str, str, int]]:
        name = self._normalize_apple_text(track.get("name", ""))
        artists = track.get("artists", []) or []
        artist = self._normalize_apple_text(artists[0].get("name", "") if artists else "")
        duration_ms = int(track.get("duration_ms") or 0)
        if not name or not artist:
            return None
        return (artist, name, round(duration_ms / 1000 / 5) if duration_ms else 0)

    def _spotify_album_apple_key(self, album: dict) -> Optional[tuple[str, str]]:
        name = self._normalize_apple_text(album.get("name", ""))
        artists = album.get("artists", []) or []
        artist = self._normalize_apple_text(artists[0].get("name", "") if artists else "")
        if not name or not artist:
            return None
        return (artist, name)

    def _apple_library_song_key(self, song: dict) -> Optional[tuple[str, str, int]]:
        attrs = song.get("attributes", {})
        name = self._normalize_apple_text(attrs.get("name", ""))
        artist = self._normalize_apple_text(attrs.get("artistName", ""))
        duration_ms = int(attrs.get("durationInMillis") or 0)
        if not name or not artist:
            return None
        return (artist, name, round(duration_ms / 1000 / 5) if duration_ms else 0)

    def _apple_library_album_key(self, album: dict) -> Optional[tuple[str, str]]:
        attrs = album.get("attributes", {})
        name = self._normalize_apple_text(attrs.get("name", ""))
        artist = self._normalize_apple_text(attrs.get("artistName", ""))
        if not name or not artist:
            return None
        return (artist, name)

    async def _get_apple_song_state(self) -> dict[str, set]:
        songs = await self.apple_music_fetcher.get_library_songs()
        ids = set()
        keys = set()
        for song in songs:
            play_params = song.get("attributes", {}).get("playParams", {})
            catalog_id = play_params.get("catalogId") or play_params.get("reportingId")
            if catalog_id:
                ids.add(str(catalog_id))
            song_id = song.get("id")
            if song_id:
                ids.add(str(song_id))
            key = self._apple_library_song_key(song)
            if key:
                keys.add(key)
        return {"ids": ids, "keys": keys}

    async def _get_apple_album_state(self) -> dict[str, set]:
        albums = await self.apple_music_fetcher.get_library_albums()
        ids = set()
        keys = set()
        for album in albums:
            album_id = album.get("id")
            if album_id:
                ids.add(str(album_id))
            key = self._apple_library_album_key(album)
            if key:
                keys.add(key)
        return {"ids": ids, "keys": keys}

    def _apple_song_exists(self, item: dict, target_id: str, state: Any) -> bool:
        track = item.get("track", item)
        if isinstance(state, dict):
            ids = state.get("ids", set())
            keys = state.get("keys", set())
        else:
            ids = state or set()
            keys = set()
        key = self._spotify_track_apple_key(track)
        return str(target_id) in ids or (key is not None and key in keys)

    def _apple_album_exists(self, item: dict, target_id: str, state: Any) -> bool:
        album = item.get("album", item)
        if isinstance(state, dict):
            ids = state.get("ids", set())
            keys = state.get("keys", set())
        else:
            ids = state or set()
            keys = set()
        key = self._spotify_album_apple_key(album)
        return str(target_id) in ids or (key is not None and key in keys)

    # ---------------------------------------------------------------------
    # Apple Music sync (Spotify -> Apple Music)
    # ---------------------------------------------------------------------

    async def sync_favorites_to_apple_music(self) -> Tuple[int, int]:
        self._require_apple_music()

        return await sync_items(
            SyncConfig(
                item_type="track",
                fetch_source=self._fetch_spotify_saved_tracks,
                # Apple Music's "library" and "favorites" are separate concepts
                # and the API has no read endpoint for favorites. If we skip
                # items based on library presence, songs that are in library
                # but not yet favorited get silently dropped — they never
                # reach add_songs_to_favorites. So always run the favorite
                # call for every matched track; it's idempotent.
                fetch_existing_ids=None,
                existing_matcher=None,
                search_item=self.apple_music_searcher.search_track,
                get_source_id=lambda item: item.get("id"),
                get_cache_match=self.cache.get_apple_track_match,
                add_item=lambda apple_id: (
                    self.apple_music.add_songs_to_library([apple_id]),
                    self.apple_music.add_songs_to_favorites([apple_id]),
                ),
                batch_add=lambda ids: (
                    self.apple_music.add_songs_to_library(ids),
                    self.apple_music.add_songs_to_favorites(ids),
                ),
                # No favorites read endpoint exists, so we can't verify the
                # favorite call took effect. The library-based verification
                # used previously here marked any favorite of an item not in
                # library (or whose key didn't match) as "not confirmed" and
                # wiped the cache entry — see sync_operations.py verify loop.
                verify_added_state=None,
                added_matcher=None,
                clear_cached_match=self.cache.remove_apple_track_match,
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
                fetch_existing_ids=(
                    self.cache.get_all_apple_album_ids
                    if self.skip_existing_check
                    else self._get_apple_album_state
                ),
                existing_matcher=self._apple_album_exists,
                search_item=lambda item: self._search_apple_album(item.get("album", {})),
                get_source_id=lambda item: item.get("album", {}).get("id"),
                get_cache_match=self.cache.get_apple_album_match,
                add_item=lambda apple_id: self.apple_music.add_albums_to_library([apple_id]),
                batch_add=lambda ids: self.apple_music.add_albums_to_library(ids),
                verify_added_state=self._get_apple_album_state,
                added_matcher=self._apple_album_exists,
                verify_poll_delays=(0.0, 3.0, 8.0, 15.0),
                clear_cached_match=self.cache.remove_apple_album_match,
                add_to_library=self.library.add_albums if self.library else None,
                add_not_found=(self.library.add_not_found_album if self.library else None),
                progress_desc="Syncing albums to Apple Music",
            ),
            self,
        )

    async def _search_apple_album(self, spotify_album: dict) -> Optional[str]:
        """Search Apple album; if standard search fails, infer via track matches."""
        if not spotify_album or not spotify_album.get("id"):
            return None
        # First try normal album search
        album_id = await self.apple_music_searcher.search_album(spotify_album)
        if album_id:
            return album_id

        # Fallback: infer album from matched tracks (first N)
        try:
            tracks = await self.spotify_fetcher.get_album_tracks(spotify_album["id"], limit=8)
        except Exception:
            tracks = []
        if not tracks:
            return None

        album_votes: dict[str, int] = {}
        for sp_track in tracks:
            try:
                am_song_id = await self.apple_music_searcher.search_track(sp_track)
            except Exception:
                am_song_id = None
            if not am_song_id:
                continue
            try:
                am_song = await retry_async_call(self.apple_music.get_catalog_song, am_song_id)
            except Exception:
                am_song = None
            if not am_song:
                continue
            rel = (am_song.get("relationships") or {}).get("albums") or {}
            data = rel.get("data") or []
            if not data:
                continue
            parent_album_id = data[0].get("id")
            if parent_album_id:
                album_votes[parent_album_id] = album_votes.get(parent_album_id, 0) + 1

        if not album_votes:
            return None
        # Return the album with the most votes
        return max(album_votes.items(), key=lambda kv: kv[1])[0]

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

        not_found_names = []

        for spotify_track in self._progress_iter(tracks, f"Matching: {playlist_name}"):
            if not isinstance(spotify_track, dict) or not spotify_track.get("id"):
                logger.debug(f"Skipping non-track item: {type(spotify_track).__name__}")
                continue

            # Search for the track on Apple Music
            try:
                apple_id = await self.apple_music_searcher.search_track(spotify_track)
            except Exception as e:
                track_name = spotify_track.get("name", "?")
                logger.warning(f"Search failed for '{track_name}': {e}")
                not_found_count += 1
                continue

            if apple_id:
                if apple_id not in existing_ids:
                    apple_ids_to_add.append(apple_id)
            else:
                not_found_count += 1
                artists = spotify_track.get("artists") or []
                artist = artists[0]["name"] if artists else "?"
                not_found_names.append(f"{artist} - {spotify_track.get('name', '?')}")
                if self.library:
                    self.library.add_not_found_track(spotify_track)

        # Log not-found tracks
        if not_found_names:
            self._log("warning", f"  {not_found_count} track(s) not found in '{playlist_name}':")
            for name in not_found_names:
                self._log("warning", f"    ✗ {name}")

        # Add tracks in order (batches of 100)
        if apple_ids_to_add:
            self.apple_music.add_tracks_to_playlist(am_playlist_id, apple_ids_to_add)
            self._log(
                "info",
                f"Added {len(apple_ids_to_add)} tracks to Apple Music playlist "
                f"'{playlist_name}'",
            )

        return (len(apple_ids_to_add), not_found_count)

    async def sync_favorites_playlist_to_apple_music(self, name: str = "Spotify Liked Songs") -> Tuple[int, int]:
        """Create or update an Apple playlist containing all Spotify liked songs in order."""
        self._require_apple_music()
        spotify_tracks = await self._fetch_spotify_saved_tracks()
        spotify_tracks = self._apply_limit(spotify_tracks)

        apple_ids_to_add: list[str] = []
        not_found_count = 0

        for track in self._progress_iter(
            spotify_tracks, f"Preparing liked songs playlist: {name}", phase="searching"
        ):
            apple_id = await self.apple_music_searcher.search_track(track)
            if apple_id:
                apple_ids_to_add.append(apple_id)
            else:
                not_found_count += 1

        if apple_ids_to_add:
            am_playlist_id = self.apple_music.get_or_create_playlist(name)
            if am_playlist_id:
                self.apple_music.add_tracks_to_playlist(am_playlist_id, apple_ids_to_add)
        return (len(apple_ids_to_add), not_found_count)

    async def sync_all_playlists_to_apple_music(
        self, skip_playlists: Optional[List[str]] = None
    ) -> dict:
        """Sync all Spotify playlists to Apple Music."""
        self._require_apple_music()
        skip_names = {s.lower() for s in (skip_playlists or [])}

        playlists = await self.spotify_fetcher.get_playlists()
        self._log("info", f"Found {len(playlists)} Spotify playlists")

        results = {}
        for i, playlist in enumerate(playlists):
            playlist_id = playlist.get("id")
            playlist_name = playlist.get("name", "Untitled")

            if playlist_name.lower() in skip_names:
                self._log("info", f"[{i + 1}/{len(playlists)}] Skipping: {playlist_name}")
                continue

            self._log("info", f"[{i + 1}/{len(playlists)}] Playlist: {playlist_name}")

            try:
                added, not_found = await self.sync_playlist_to_apple_music(playlist_id)
                results[playlist_name] = {
                    "added": added,
                    "not_found": not_found,
                }
            except Exception as e:
                self._log("error", f"Failed to sync playlist '{playlist_name}': {e}")
                results[playlist_name] = {"error": str(e)}

            # Brief cooldown between playlists to avoid API throttling
            if i < len(playlists) - 1:
                import asyncio

                await asyncio.sleep(2)

        return results
