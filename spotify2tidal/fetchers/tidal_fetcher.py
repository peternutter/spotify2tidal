"""Fetcher for extracting data from Tidal with proper pagination."""

import logging
from typing import Callable, List, Optional, Set

import tidalapi

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

        Tidal's favorites.tracks() only returns the first page (~100 items).
        We need to paginate to get all favorites for proper duplicate detection.
        """
        all_ids: Set[int] = set()
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.tracks(limit=limit, offset=offset)
            if not page:
                break

            for track in page:
                all_ids.add(track.id)

            self._log_progress(f"Fetching Tidal favorites: {len(all_ids)} tracks...")

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def get_favorite_album_ids(self) -> Set[int]:
        """Get ALL favorite album IDs from Tidal with proper pagination."""
        all_ids: Set[int] = set()
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.albums(limit=limit, offset=offset)
            if not page:
                break

            for album in page:
                all_ids.add(album.id)

            self._log_progress(
                f"Fetching Tidal album favorites: {len(all_ids)} albums..."
            )

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def get_favorite_artist_ids(self) -> Set[int]:
        """Get ALL favorite artist IDs from Tidal with proper pagination."""
        all_ids: Set[int] = set()
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.artists(limit=limit, offset=offset)
            if not page:
                break

            for artist in page:
                all_ids.add(artist.id)

            self._log_progress(
                f"Fetching Tidal artist favorites: {len(all_ids)} artists..."
            )

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def get_playlist_track_ids(self, playlist: tidalapi.Playlist) -> Set[int]:
        """Get ALL track IDs from a Tidal playlist with proper pagination."""
        all_ids: Set[int] = set()
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

    async def get_favorite_tracks(self) -> List[tidalapi.Track]:
        """Get ALL favorite tracks from Tidal (full objects, not just IDs)."""
        all_tracks: List[tidalapi.Track] = []
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.tracks(limit=limit, offset=offset)
            if not page:
                break

            all_tracks.extend(page)
            self._log_progress(f"Fetching Tidal tracks: {len(all_tracks)}...")

            if len(page) < limit:
                break
            offset += limit

        return all_tracks

    async def get_favorite_albums(self) -> List[tidalapi.Album]:
        """Get ALL favorite albums from Tidal (full objects, not just IDs)."""
        all_albums: List[tidalapi.Album] = []
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.albums(limit=limit, offset=offset)
            if not page:
                break

            all_albums.extend(page)
            self._log_progress(f"Fetching Tidal albums: {len(all_albums)}...")

            if len(page) < limit:
                break
            offset += limit

        return all_albums

    async def get_favorite_artists(self) -> List[tidalapi.Artist]:
        """Get ALL favorite artists from Tidal (full objects, not just IDs)."""
        all_artists: List[tidalapi.Artist] = []
        limit = 100
        offset = 0

        while True:
            page = self.tidal.user.favorites.artists(limit=limit, offset=offset)
            if not page:
                break

            all_artists.extend(page)
            self._log_progress(f"Fetching Tidal artists: {len(all_artists)}...")

            if len(page) < limit:
                break
            offset += limit

        return all_artists
