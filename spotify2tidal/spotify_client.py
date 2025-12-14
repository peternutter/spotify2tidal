"""
Spotify API client wrapper.

Provides paginated data fetching for all Spotify library endpoints.
"""

import logging
from typing import List, Set

import spotipy

logger = logging.getLogger(__name__)


class SpotifyClient:
    """Wrapper for Spotify API with paginated data fetching."""

    def __init__(self, session: spotipy.Spotify, log_callback=None):
        self.session = session
        self._log_callback = log_callback

    def _log(self, level: str, message: str):
        """Log a message."""
        if self._log_callback:
            self._log_callback(level, message)
        else:
            getattr(logger, level)(message)

    # =========================================================================
    # Fetching library data
    # =========================================================================

    async def get_saved_tracks(self) -> List[dict]:
        """Get all saved/liked tracks from Spotify."""
        tracks = []
        results = self.session.current_user_saved_tracks()

        while True:
            for item in results["items"]:
                if item["track"]:
                    tracks.append(item["track"])

            self._log("progress", f"Fetching saved tracks: {len(tracks)} tracks...")

            if not results["next"]:
                break
            results = self.session.next(results)

        return tracks

    async def get_saved_albums(self) -> List[dict]:
        """Get all saved albums from Spotify."""
        albums = []
        results = self.session.current_user_saved_albums()

        while True:
            albums.extend(results["items"])
            self._log("progress", f"Fetching saved albums: {len(albums)} albums...")

            if not results["next"]:
                break
            results = self.session.next(results)

        return albums

    async def get_followed_artists(self) -> List[dict]:
        """Get all followed artists from Spotify."""
        artists = []
        results = self.session.current_user_followed_artists()["artists"]

        while True:
            artists.extend(results["items"])
            self._log(
                "progress", f"Fetching followed artists: {len(artists)} artists..."
            )

            if not results["next"]:
                break
            results = self.session.next(results)["artists"]

        return artists

    async def get_saved_shows(self) -> List[dict]:
        """Get all saved shows/podcasts from Spotify."""
        shows = []
        try:
            results = self.session.current_user_saved_shows()

            while True:
                shows.extend(results["items"])
                self._log("progress", f"Fetching saved podcasts: {len(shows)} shows...")

                if not results["next"]:
                    break
                results = self.session.next(results)
        except Exception as e:
            logger.warning(f"Could not fetch podcasts (may need to re-auth): {e}")

        return shows

    async def get_playlist_tracks(self, playlist_id: str) -> List[dict]:
        """Get all tracks from a Spotify playlist."""
        tracks = []
        results = self.session.playlist_tracks(playlist_id)

        while True:
            for item in results["items"]:
                if item["track"] and item["track"].get("type") == "track":
                    tracks.append(item["track"])

            if not results["next"]:
                break
            results = self.session.next(results)

        return tracks

    # =========================================================================
    # Getting existing IDs (for duplicate detection)
    # =========================================================================

    async def get_saved_track_ids(self) -> Set[str]:
        """Get ALL saved track IDs from Spotify."""
        all_ids = set()
        results = self.session.current_user_saved_tracks()

        while True:
            for item in results["items"]:
                if item["track"]:
                    all_ids.add(item["track"]["id"])

            self._log("progress", f"Fetching Spotify tracks: {len(all_ids)}...")

            if not results["next"]:
                break
            results = self.session.next(results)

        return all_ids

    async def get_saved_album_ids(self) -> Set[str]:
        """Get ALL saved album IDs from Spotify."""
        all_ids = set()
        results = self.session.current_user_saved_albums()

        while True:
            for item in results["items"]:
                if item["album"]:
                    all_ids.add(item["album"]["id"])

            self._log("progress", f"Fetching Spotify albums: {len(all_ids)}...")

            if not results["next"]:
                break
            results = self.session.next(results)

        return all_ids

    async def get_followed_artist_ids(self) -> Set[str]:
        """Get ALL followed artist IDs from Spotify."""
        all_ids = set()
        results = self.session.current_user_followed_artists()["artists"]

        while True:
            for artist in results["items"]:
                all_ids.add(artist["id"])

            self._log("progress", f"Fetching Spotify artists: {len(all_ids)}...")

            if not results["next"]:
                break
            results = self.session.next(results)["artists"]

        return all_ids

    # =========================================================================
    # Adding to library
    # =========================================================================

    def add_tracks(self, track_ids: List[str]):
        """Add tracks to user's saved tracks (batch of up to 50)."""
        self.session.current_user_saved_tracks_add(tracks=track_ids)

    def add_albums(self, album_ids: List[str]):
        """Add albums to user's saved albums (batch of up to 50)."""
        self.session.current_user_saved_albums_add(albums=album_ids)

    def follow_artists(self, artist_ids: List[str]):
        """Follow artists (batch of up to 50)."""
        self.session.user_follow_artists(ids=artist_ids)
