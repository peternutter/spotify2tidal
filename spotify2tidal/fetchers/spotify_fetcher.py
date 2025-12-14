"""Fetcher for extracting data from Spotify with proper pagination."""

import logging
from typing import Callable, List, Optional, Set

import spotipy

logger = logging.getLogger(__name__)


class SpotifyFetcher:
    """
    Fetches data from Spotify with proper pagination.

    Consolidates all paginated fetching logic for Spotify API calls.
    """

    def __init__(
        self,
        spotify: spotipy.Spotify,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Spotify fetcher.

        Args:
            spotify: Authenticated Spotify client
            progress_callback: Optional callback for progress messages
        """
        self.spotify = spotify
        self._progress_callback = progress_callback

    def _log_progress(self, message: str):
        """Report progress if callback is available."""
        if self._progress_callback:
            self._progress_callback(message)

    async def get_saved_tracks(self) -> List[dict]:
        """Get all saved/liked tracks from Spotify."""
        tracks = []
        results = self.spotify.current_user_saved_tracks()

        while True:
            for item in results["items"]:
                if item["track"]:
                    tracks.append(item["track"])

            self._log_progress(f"Fetching saved tracks: {len(tracks)} tracks...")

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return tracks

    async def get_saved_albums(self) -> List[dict]:
        """Get all saved albums from Spotify."""
        albums = []
        results = self.spotify.current_user_saved_albums()

        while True:
            albums.extend(results["items"])
            self._log_progress(f"Fetching saved albums: {len(albums)} albums...")

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return albums

    async def get_followed_artists(self) -> List[dict]:
        """Get all followed artists from Spotify."""
        artists = []
        results = self.spotify.current_user_followed_artists()["artists"]

        while True:
            artists.extend(results["items"])
            self._log_progress(f"Fetching followed artists: {len(artists)} artists...")

            if not results["next"]:
                break
            results = self.spotify.next(results)["artists"]

        return artists

    async def get_playlist_tracks(self, playlist_id: str) -> List[dict]:
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

    async def get_saved_shows(self) -> List[dict]:
        """Get all saved shows/podcasts from Spotify."""
        shows = []
        try:
            results = self.spotify.current_user_saved_shows()

            while True:
                shows.extend(results["items"])
                self._log_progress(f"Fetching saved podcasts: {len(shows)} shows...")

                if not results["next"]:
                    break
                results = self.spotify.next(results)
        except Exception as e:
            logger.warning(f"Could not fetch podcasts (may need to re-auth): {e}")

        return shows

    async def get_saved_track_ids(self) -> Set[str]:
        """Get ALL saved track IDs from Spotify."""
        all_ids: Set[str] = set()
        results = self.spotify.current_user_saved_tracks()

        while True:
            for item in results["items"]:
                if item["track"] and item["track"].get("id"):
                    all_ids.add(item["track"]["id"])

            self._log_progress(f"Fetching Spotify track IDs: {len(all_ids)} tracks...")

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return all_ids

    async def get_saved_album_ids(self) -> Set[str]:
        """Get ALL saved album IDs from Spotify."""
        all_ids: Set[str] = set()
        results = self.spotify.current_user_saved_albums()

        while True:
            for item in results["items"]:
                if item.get("album") and item["album"].get("id"):
                    all_ids.add(item["album"]["id"])

            self._log_progress(f"Fetching Spotify album IDs: {len(all_ids)} albums...")

            if not results["next"]:
                break
            results = self.spotify.next(results)

        return all_ids

    async def get_followed_artist_ids(self) -> Set[str]:
        """Get ALL followed artist IDs from Spotify."""
        all_ids: Set[str] = set()
        results = self.spotify.current_user_followed_artists()["artists"]

        while True:
            for artist in results["items"]:
                if artist.get("id"):
                    all_ids.add(artist["id"])

            self._log_progress(
                f"Fetching Spotify artist IDs: {len(all_ids)} artists..."
            )

            if not results["next"]:
                break
            results = self.spotify.next(results)["artists"]

        return all_ids
