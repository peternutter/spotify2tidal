"""
Async wrapper for Apple Music API client with pagination and limits.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Callable, List, Optional, Set

if TYPE_CHECKING:
    from ..apple_music_client import AppleMusicClient

logger = logging.getLogger(__name__)


class AppleMusicFetcher:
    """Async fetcher for Apple Music library data."""

    def __init__(
        self,
        client: "AppleMusicClient",
        progress_callback: Optional[Callable] = None,
    ):
        self.client = client
        self.progress_callback = progress_callback

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def get_library_songs(self, limit: Optional[int] = None) -> List[dict]:
        """Fetch all songs from the user's Apple Music library."""
        songs = await self._run_sync(self.client.get_library_songs, limit=limit)
        if self.progress_callback:
            self.progress_callback(f"Fetched {len(songs)} Apple Music library songs")
        return songs

    async def get_library_albums(self, limit: Optional[int] = None) -> List[dict]:
        """Fetch all albums from the user's Apple Music library."""
        albums = await self._run_sync(self.client.get_library_albums, limit=limit)
        if self.progress_callback:
            self.progress_callback(f"Fetched {len(albums)} Apple Music library albums")
        return albums

    async def get_playlists(self, limit: Optional[int] = None) -> List[dict]:
        """Fetch all playlists from the user's Apple Music library."""
        playlists = await self._run_sync(self.client.get_library_playlists, limit=limit)
        if self.progress_callback:
            self.progress_callback(f"Fetched {len(playlists)} Apple Music playlists")
        return playlists

    async def get_playlist_tracks(
        self, playlist_id: str, limit: Optional[int] = None
    ) -> List[dict]:
        """Fetch all tracks from a specific playlist."""
        tracks = await self._run_sync(self.client.get_playlist_tracks, playlist_id, limit=limit)
        return tracks

    async def get_library_song_ids(self) -> Set[str]:
        """Fetch catalog IDs of all songs in the user's library."""
        return await self._run_sync(self.client.get_library_song_ids)

    async def get_library_album_ids(self) -> Set[str]:
        """Fetch IDs of all albums in the user's library."""
        albums = await self._run_sync(self.client.get_library_albums)
        ids = set()
        for album in albums:
            play_params = album.get("attributes", {}).get("playParams", {})
            catalog_id = play_params.get("catalogId")
            if catalog_id:
                ids.add(str(catalog_id))
            album_id = album.get("id")
            if album_id:
                ids.add(str(album_id))
        return ids

    async def get_playlist_track_ids(self, playlist_id: str) -> Set[str]:
        """Fetch catalog IDs of all tracks in a playlist."""
        return await self._run_sync(self.client.get_library_playlist_track_ids, playlist_id)
