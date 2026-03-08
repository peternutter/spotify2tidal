"""Fetcher for extracting data from Tidal with proper pagination."""

import logging
from typing import Callable, List, Optional, Set

import tidalapi

from ..retry_utils import retry_async_call

logger = logging.getLogger(__name__)


async def _paginate_tidal(
    fetch_fn,
    total_count: int,
    label: str,
    progress_fn=None,
    limit: int = 100,
    limit_total: Optional[int] = None,
) -> list:
    """Generic Tidal offset-based pagination.

    Uses a known ``total_count`` (from the count API) to avoid the
    ``len(page) < limit`` bug where Tidal returns short pages mid-stream.
    Logs a warning if the fetched count is <90% of the expected total.
    """
    items: list = []
    offset = 0

    while offset < total_count:
        page = await retry_async_call(fetch_fn, limit=limit, offset=offset)
        if not page:
            break

        items.extend(page)

        if limit_total and len(items) >= limit_total:
            if progress_fn:
                progress_fn(f"{label} (limited): {len(items)}...")
            return items[:limit_total]

        if progress_fn:
            progress_fn(f"{label}: {len(items)}/{total_count}...")

        offset += limit

    if len(items) < total_count * 0.9:
        logger.warning(f"{label}: expected ~{total_count}, got {len(items)}")
    return items


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
        self.tidal = tidal
        self._progress_callback = progress_callback

    def _log_progress(self, message: str):
        """Report progress if callback is available."""
        if self._progress_callback:
            self._progress_callback(message)

    # ------------------------------------------------------------------
    # IDs (sets)
    # ------------------------------------------------------------------

    async def get_favorite_track_ids(self) -> Set[int]:
        """Get ALL favorite track IDs from Tidal."""
        total = await retry_async_call(self.tidal.user.favorites.get_tracks_count)
        items = await _paginate_tidal(
            self.tidal.user.favorites.tracks, total, "Fetching Tidal track IDs", self._log_progress
        )
        return {t.id for t in items}

    async def get_favorite_album_ids(self) -> Set[int]:
        """Get ALL favorite album IDs from Tidal."""
        total = await retry_async_call(self.tidal.user.favorites.get_albums_count)
        items = await _paginate_tidal(
            self.tidal.user.favorites.albums, total, "Fetching Tidal album IDs", self._log_progress
        )
        return {a.id for a in items}

    async def get_favorite_artist_ids(self) -> Set[int]:
        """Get ALL favorite artist IDs from Tidal."""
        total = await retry_async_call(self.tidal.user.favorites.get_artists_count)
        items = await _paginate_tidal(
            self.tidal.user.favorites.artists,
            total,
            "Fetching Tidal artist IDs",
            self._log_progress,
        )
        return {a.id for a in items}

    async def get_playlist_track_ids(self, playlist: tidalapi.Playlist) -> Set[int]:
        """Get ALL track IDs from a Tidal playlist."""
        total = getattr(playlist, "num_tracks", None) or 0
        items = await _paginate_tidal(playlist.tracks, max(total, 1), "Playlist track IDs")
        return {t.id for t in items}

    # ------------------------------------------------------------------
    # Full objects (lists, ordered)
    # ------------------------------------------------------------------

    async def get_favorite_tracks(self, limit_total: Optional[int] = None) -> List[tidalapi.Track]:
        """Get favorite tracks from Tidal (full objects, optionally limited)."""
        total = await retry_async_call(self.tidal.user.favorites.get_tracks_count)
        self._log_progress(f"Tidal reports {total} favorite tracks")
        return await _paginate_tidal(
            self.tidal.user.favorites.tracks,
            total,
            "Fetching Tidal tracks",
            self._log_progress,
            limit_total=limit_total,
        )

    async def get_favorite_albums(self, limit_total: Optional[int] = None) -> List[tidalapi.Album]:
        """Get favorite albums from Tidal (full objects, optionally limited)."""
        total = await retry_async_call(self.tidal.user.favorites.get_albums_count)
        return await _paginate_tidal(
            self.tidal.user.favorites.albums,
            total,
            "Fetching Tidal albums",
            self._log_progress,
            limit_total=limit_total,
        )

    async def get_favorite_artists(
        self, limit_total: Optional[int] = None
    ) -> List[tidalapi.Artist]:
        """Get favorite artists from Tidal (full objects, optionally limited)."""
        total = await retry_async_call(self.tidal.user.favorites.get_artists_count)
        return await _paginate_tidal(
            self.tidal.user.favorites.artists,
            total,
            "Fetching Tidal artists",
            self._log_progress,
            limit_total=limit_total,
        )

    async def get_playlist_tracks(
        self, playlist: tidalapi.Playlist, limit_total: Optional[int] = None
    ) -> List[tidalapi.Track]:
        """Get ALL tracks from a Tidal playlist (in order)."""
        total = getattr(playlist, "num_tracks", None) or 0
        return await _paginate_tidal(
            playlist.tracks,
            max(total, 1),
            "Playlist tracks",
            limit_total=limit_total,
        )

    async def get_playlists(self, limit: Optional[int] = None) -> List[tidalapi.Playlist]:
        """Get ALL user playlists from Tidal (optionally limited)."""
        playlists = list(await retry_async_call(self.tidal.user.playlists))
        if limit:
            return playlists[:limit]
        return playlists
