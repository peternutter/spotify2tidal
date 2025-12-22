"""
Tidal API client wrapper.

Provides paginated data fetching for all Tidal library endpoints.
"""

import logging
from typing import List, Set

import tidalapi

logger = logging.getLogger(__name__)


class TidalClient:
    """Wrapper for Tidal API with paginated data fetching."""

    def __init__(self, session: tidalapi.Session, log_callback=None):
        self.session = session
        self._log_callback = log_callback

    def _log(self, level: str, message: str):
        """Log a message."""
        if self._log_callback:
            self._log_callback(level, message)
        else:
            getattr(logger, level)(message)

    # =========================================================================
    # Fetching library data (full objects)
    # =========================================================================

    async def get_favorite_tracks(self) -> List[tidalapi.Track]:
        """Get ALL favorite tracks from Tidal (full objects)."""
        all_tracks = []
        limit = 100
        offset = 0

        while True:
            page = self.session.user.favorites.tracks(limit=limit, offset=offset)
            if not page:
                break
            all_tracks.extend(page)
            self._log("progress", f"Fetching Tidal tracks: {len(all_tracks)}...")
            if len(page) < limit:
                break
            offset += limit

        return all_tracks

    async def get_favorite_albums(self) -> List[tidalapi.Album]:
        """Get ALL favorite albums from Tidal (full objects)."""
        all_albums = []
        limit = 100
        offset = 0

        while True:
            page = self.session.user.favorites.albums(limit=limit, offset=offset)
            if not page:
                break
            all_albums.extend(page)
            self._log("progress", f"Fetching Tidal albums: {len(all_albums)}...")
            if len(page) < limit:
                break
            offset += limit

        return all_albums

    async def get_favorite_artists(self) -> List[tidalapi.Artist]:
        """Get ALL favorite artists from Tidal (full objects)."""
        all_artists = []
        limit = 100
        offset = 0

        while True:
            page = self.session.user.favorites.artists(limit=limit, offset=offset)
            if not page:
                break
            all_artists.extend(page)
            self._log("progress", f"Fetching Tidal artists: {len(all_artists)}...")
            if len(page) < limit:
                break
            offset += limit

        return all_artists

    # =========================================================================
    # Getting existing IDs (for duplicate detection)
    # =========================================================================

    async def get_favorite_track_ids(self) -> Set[int]:
        """Get ALL favorite track IDs from Tidal."""
        all_ids = set()
        limit = 100
        offset = 0

        while True:
            page = self.session.user.favorites.tracks(limit=limit, offset=offset)
            if not page:
                break

            for track in page:
                all_ids.add(track.id)

            self._log("progress", f"Fetching Tidal favorites: {len(all_ids)} tracks...")

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def get_favorite_album_ids(self) -> Set[int]:
        """Get ALL favorite album IDs from Tidal."""
        all_ids = set()
        limit = 100
        offset = 0

        while True:
            page = self.session.user.favorites.albums(limit=limit, offset=offset)
            if not page:
                break

            for album in page:
                all_ids.add(album.id)

            self._log(
                "progress", f"Fetching Tidal album favorites: {len(all_ids)} albums..."
            )

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def get_favorite_artist_ids(self) -> Set[int]:
        """Get ALL favorite artist IDs from Tidal."""
        all_ids = set()
        limit = 100
        offset = 0

        while True:
            page = self.session.user.favorites.artists(limit=limit, offset=offset)
            if not page:
                break

            for artist in page:
                all_ids.add(artist.id)

            self._log(
                "progress",
                f"Fetching Tidal artist favorites: {len(all_ids)} artists...",
            )

            if len(page) < limit:
                break
            offset += limit

        return all_ids

    async def get_playlist_track_ids(self, playlist: tidalapi.Playlist) -> Set[int]:
        """Get ALL track IDs from a Tidal playlist."""
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

    # =========================================================================
    # Adding to library
    # =========================================================================

    def add_track(self, track_id: int):
        """Add a track to favorites."""
        self.session.user.favorites.add_track(track_id)

    def add_album(self, album_id: int):
        """Add an album to favorites."""
        self.session.user.favorites.add_album(album_id)

    def add_artist(self, artist_id: int):
        """Add an artist to favorites."""
        self.session.user.favorites.add_artist(artist_id)

    # =========================================================================
    # Playlist management
    # =========================================================================

    async def get_playlists(self) -> List[tidalapi.Playlist]:
        """Get all user playlists."""
        return list(self.session.user.playlists())

    async def get_or_create_playlist(self, name: str) -> tidalapi.Playlist:
        """Find existing playlist by name or create new one."""
        playlists = await self.get_playlists()
        for playlist in playlists:
            if playlist.name == name:
                return playlist

        return self.session.user.create_playlist(name, "")

    def add_tracks_to_playlist(self, playlist: tidalapi.Playlist, track_ids: List[int]):
        """Add tracks to a playlist."""
        playlist.add(track_ids)
