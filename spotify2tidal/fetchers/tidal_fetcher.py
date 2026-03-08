"""Fetcher for extracting data from Tidal with proper pagination."""

import logging
from typing import Callable, List, Optional, Set

import tidalapi

from ..retry_utils import retry_async_call

logger = logging.getLogger(__name__)


class TidalFetcher:
    """
    Fetches data from Tidal with proper pagination.

    Consolidates all paginated fetching logic for Tidal API calls.
    """

    def __init__(
        self,
        tidal: tidalapi.Session,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Tidal fetcher.

        Args:
            tidal: Authenticated Tidal session
            progress_callback: Optional callback for progress messages
        """
        self.tidal = tidal
        self._progress_callback = progress_callback

    def _log_progress(self, message: str):
        """Report progress if callback is available."""
        if self._progress_callback:
            self._progress_callback(message)

    async def get_favorite_track_ids(self) -> Set[int]:
        """
        Get ALL favorite track IDs from Tidal with proper pagination.

        Uses get_tracks_count() to know the total, since Tidal may return
        fewer items than ``limit`` on a page without being done.
        """
        total_count = await retry_async_call(self.tidal.user.favorites.get_tracks_count)
        all_ids: Set[int] = set()
        limit = 100
        offset = 0

        while offset < total_count:
            page = await retry_async_call(
                self.tidal.user.favorites.tracks, limit=limit, offset=offset
            )
            if not page:
                break

            for track in page:
                all_ids.add(track.id)

            self._log_progress(f"Fetching Tidal favorites: {len(all_ids)}/{total_count} tracks...")

            offset += limit

        if len(all_ids) < total_count * 0.9:
            logger.warning(f"Track IDs: expected ~{total_count}, got {len(all_ids)}")
        return all_ids

    async def get_favorite_album_ids(self) -> Set[int]:
        """Get ALL favorite album IDs from Tidal with proper pagination."""
        total_count = await retry_async_call(self.tidal.user.favorites.get_albums_count)
        all_ids: Set[int] = set()
        limit = 100
        offset = 0

        while offset < total_count:
            page = await retry_async_call(
                self.tidal.user.favorites.albums, limit=limit, offset=offset
            )
            if not page:
                break

            for album in page:
                all_ids.add(album.id)

            self._log_progress(
                f"Fetching Tidal album favorites: {len(all_ids)}/{total_count} albums..."
            )

            offset += limit

        if len(all_ids) < total_count * 0.9:
            logger.warning(f"Album IDs: expected ~{total_count}, got {len(all_ids)}")
        return all_ids

    async def get_favorite_artist_ids(self) -> Set[int]:
        """Get ALL favorite artist IDs from Tidal with proper pagination."""
        total_count = await retry_async_call(self.tidal.user.favorites.get_artists_count)
        all_ids: Set[int] = set()
        limit = 100
        offset = 0

        while offset < total_count:
            page = await retry_async_call(
                self.tidal.user.favorites.artists, limit=limit, offset=offset
            )
            if not page:
                break

            for artist in page:
                all_ids.add(artist.id)

            self._log_progress(
                f"Fetching Tidal artist favorites: {len(all_ids)}/{total_count} artists..."
            )

            offset += limit

        if len(all_ids) < total_count * 0.9:
            logger.warning(f"Artist IDs: expected ~{total_count}, got {len(all_ids)}")
        return all_ids

    async def get_playlist_track_ids(self, playlist: tidalapi.Playlist) -> Set[int]:
        """Get ALL track IDs from a Tidal playlist with proper pagination."""
        total_count = getattr(playlist, "num_tracks", None) or 0
        all_ids: Set[int] = set()
        limit = 100
        offset = 0

        while offset < max(total_count, 1):
            page = await retry_async_call(playlist.tracks, limit=limit, offset=offset)
            if not page:
                break

            for track in page:
                all_ids.add(track.id)

            offset += limit

        if total_count and len(all_ids) < total_count * 0.9:
            logger.warning(f"Playlist track IDs: expected ~{total_count}, got {len(all_ids)}")
        return all_ids

    async def get_playlist_tracks(
        self, playlist: tidalapi.Playlist, limit_total: Optional[int] = None
    ) -> List[tidalapi.Track]:
        """Get ALL tracks from a Tidal playlist with proper pagination (in order)."""
        total_count = getattr(playlist, "num_tracks", None) or 0
        tracks: List[tidalapi.Track] = []
        limit = 100
        offset = 0

        while offset < max(total_count, 1):
            page = await retry_async_call(playlist.tracks, limit=limit, offset=offset)
            if not page:
                break

            tracks.extend(page)

            if limit_total and len(tracks) >= limit_total:
                return tracks[:limit_total]

            offset += limit

        if total_count and len(tracks) < total_count * 0.9:
            logger.warning(f"Playlist tracks: expected ~{total_count}, got {len(tracks)}")
        return tracks

    async def get_favorite_tracks(self, limit_total: Optional[int] = None) -> List[tidalapi.Track]:
        """Get favorite tracks from Tidal (full objects, optionally limited)."""
        # Get the actual total count first to paginate correctly
        # (Tidal may return fewer items than `limit` on a page without being done)
        total_count = await retry_async_call(self.tidal.user.favorites.get_tracks_count)
        self._log_progress(f"Tidal reports {total_count} favorite tracks")

        all_tracks: List[tidalapi.Track] = []
        limit = 100
        offset = 0

        while offset < total_count:
            page = await retry_async_call(
                self.tidal.user.favorites.tracks, limit=limit, offset=offset
            )
            if not page:
                break

            all_tracks.extend(page)
            if limit_total and len(all_tracks) >= limit_total:
                self._log_progress(f"Fetching Tidal tracks (limited): {len(all_tracks)}...")
                return all_tracks[:limit_total]
            self._log_progress(f"Fetching Tidal tracks: {len(all_tracks)}/{total_count}...")

            offset += limit

        if len(all_tracks) < total_count * 0.9:
            logger.warning(f"Tracks: expected ~{total_count}, got {len(all_tracks)}")
        return all_tracks

    async def get_favorite_albums(self, limit_total: Optional[int] = None) -> List[tidalapi.Album]:
        """Get favorite albums from Tidal (full objects, optionally limited)."""
        total_count = await retry_async_call(self.tidal.user.favorites.get_albums_count)
        all_albums: List[tidalapi.Album] = []
        limit = 100
        offset = 0

        while offset < total_count:
            page = await retry_async_call(
                self.tidal.user.favorites.albums, limit=limit, offset=offset
            )
            if not page:
                break

            all_albums.extend(page)
            if limit_total and len(all_albums) >= limit_total:
                self._log_progress(f"Fetching Tidal albums (limited): {len(all_albums)}...")
                return all_albums[:limit_total]
            self._log_progress(f"Fetching Tidal albums: {len(all_albums)}/{total_count}...")

            offset += limit

        if len(all_albums) < total_count * 0.9:
            logger.warning(f"Albums: expected ~{total_count}, got {len(all_albums)}")
        return all_albums

    async def get_favorite_artists(
        self, limit_total: Optional[int] = None
    ) -> List[tidalapi.Artist]:
        """Get favorite artists from Tidal (full objects, optionally limited)."""
        total_count = await retry_async_call(self.tidal.user.favorites.get_artists_count)
        all_artists: List[tidalapi.Artist] = []
        limit = 100
        offset = 0

        while offset < total_count:
            page = await retry_async_call(
                self.tidal.user.favorites.artists, limit=limit, offset=offset
            )
            if not page:
                break

            all_artists.extend(page)
            if limit_total and len(all_artists) >= limit_total:
                self._log_progress(f"Fetching Tidal artists (limited): {len(all_artists)}...")
                return all_artists[:limit_total]
            self._log_progress(f"Fetching Tidal artists: {len(all_artists)}/{total_count}...")

            offset += limit

        if len(all_artists) < total_count * 0.9:
            logger.warning(f"Artists: expected ~{total_count}, got {len(all_artists)}")
        return all_artists

    async def get_playlists(self, limit: Optional[int] = None) -> List[tidalapi.Playlist]:
        """Get ALL user playlists from Tidal (optionally limited, paginated)."""
        # Note: Tidal's user.playlists() currently returns a simple list in the
        # python lib, but we add this for consistency and future-proofing in
        # case they add pagination.
        playlists = list(await retry_async_call(self.tidal.user.playlists))
        if limit:
            return playlists[:limit]
        return playlists
