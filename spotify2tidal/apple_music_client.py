"""
Apple Music API client using cookie-based authentication.

Tokens are extracted from browser DevTools on https://buy.music.apple.com/account/web/info.
See README for instructions.
"""

import logging
import time
from typing import List, Optional, Set
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://amp-api.music.apple.com"


class AppleMusicClient:
    """Lightweight Apple Music API client using browser-extracted tokens."""

    def __init__(
        self,
        bearer_token: str,
        media_user_token: str,
        cookies: str,
        storefront: str = "us",
    ):
        self.storefront = storefront
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {bearer_token}"
                if not bearer_token.startswith("Bearer ")
                else bearer_token,
                "Media-User-Token": media_user_token,
                "Cookie": cookies,
                "Origin": "https://music.apple.com",
                "Referer": "https://music.apple.com/",
                "Host": "amp-api.music.apple.com",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )

    def _request(self, method: str, url: str, max_retries: int = 5, **kwargs) -> dict:
        """Make an API request with rate limit retry."""
        for attempt in range(max_retries):
            resp = self.session.request(method, url, **kwargs)

            if resp.status_code == 429:
                wait = min(2**attempt, 30)
                logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
                continue

            if resp.status_code == 401:
                raise AuthenticationError(
                    "Apple Music authentication failed. "
                    "Your tokens may have expired. "
                    "Re-extract them from browser DevTools."
                )

            if resp.status_code == 403:
                raise AuthenticationError(
                    "Apple Music access forbidden. " "Check your Media-User-Token and cookies."
                )

            if resp.status_code in (200, 201, 202, 204):
                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

            # Other errors
            try:
                error_data = resp.json()
                error_msg = error_data.get("errors", [{}])[0].get("detail", resp.text)
            except Exception:
                error_msg = resp.text
            raise AppleMusicAPIError(f"Apple Music API error {resp.status_code}: {error_msg}")

        raise AppleMusicAPIError("Max retries exceeded due to rate limiting")

    def _get_paginated(self, url: str, limit: Optional[int] = None) -> List[dict]:
        """Fetch all pages of a paginated endpoint."""
        results = []
        next_url = url

        while next_url:
            data = self._request("GET", next_url)
            items = data.get("data", [])
            results.extend(items)

            if limit and len(results) >= limit:
                return results[:limit]

            next_href = data.get("next")
            if next_href:
                next_url = f"{BASE_URL}{next_href}"
            else:
                break

        return results

    # =========================================================================
    # Catalog operations (search / lookup)
    # =========================================================================

    def search_catalog_by_isrc(self, isrc: str) -> Optional[dict]:
        """Search for a song by ISRC code. Returns first match or None."""
        url = f"{BASE_URL}/v1/catalog/{self.storefront}/songs" f"?filter[isrc]={isrc}"
        try:
            data = self._request("GET", url)
            items = data.get("data", [])
            return items[0] if items else None
        except AppleMusicAPIError as e:
            logger.debug(f"ISRC search failed for {isrc}: {e}")
            return None

    def search_catalog(self, query: str, types: str = "songs", limit: int = 10) -> List[dict]:
        """Search the Apple Music catalog."""
        url = (
            f"{BASE_URL}/v1/catalog/{self.storefront}/search"
            f"?term={quote(query)}&types={types}&limit={limit}"
        )
        try:
            data = self._request("GET", url)
            # Results are nested under the type key
            results = data.get("results", {})
            return results.get(types, {}).get("data", [])
        except AppleMusicAPIError as e:
            logger.debug(f"Catalog search failed for '{query}': {e}")
            return []

    def get_catalog_song(self, song_id: str) -> Optional[dict]:
        """Get a specific catalog song by ID."""
        url = f"{BASE_URL}/v1/catalog/{self.storefront}/songs/{song_id}"
        try:
            data = self._request("GET", url)
            items = data.get("data", [])
            return items[0] if items else None
        except AppleMusicAPIError as e:
            logger.debug(f"Failed to get song {song_id}: {e}")
            return None

    # =========================================================================
    # Library operations (read user library)
    # =========================================================================

    def get_library_songs(self, limit: Optional[int] = None) -> List[dict]:
        """Get all songs in the user's library."""
        url = f"{BASE_URL}/v1/me/library/songs?limit=100"
        return self._get_paginated(url, limit=limit)

    def get_library_albums(self, limit: Optional[int] = None) -> List[dict]:
        """Get all albums in the user's library."""
        url = f"{BASE_URL}/v1/me/library/albums?limit=100"
        return self._get_paginated(url, limit=limit)

    def get_library_playlists(self, limit: Optional[int] = None) -> List[dict]:
        """Get all playlists in the user's library."""
        url = f"{BASE_URL}/v1/me/library/playlists?limit=100"
        return self._get_paginated(url, limit=limit)

    def get_playlist_tracks(self, playlist_id: str, limit: Optional[int] = None) -> List[dict]:
        """Get all tracks in a library playlist."""
        url = f"{BASE_URL}/v1/me/library/playlists/{playlist_id}/tracks?limit=100"
        return self._get_paginated(url, limit=limit)

    def get_library_song_ids(self) -> Set[str]:
        """Get catalog IDs of all songs in the user's library."""
        songs = self.get_library_songs()
        ids = set()
        for song in songs:
            # Library songs have a catalogId in playParams
            play_params = song.get("attributes", {}).get("playParams", {})
            catalog_id = play_params.get("catalogId")
            if catalog_id:
                ids.add(str(catalog_id))
            # Also track the library ID itself
            song_id = song.get("id")
            if song_id:
                ids.add(str(song_id))
        return ids

    def get_library_playlist_track_ids(self, playlist_id: str) -> Set[str]:
        """Get catalog IDs of all tracks in a library playlist."""
        tracks = self.get_playlist_tracks(playlist_id)
        ids = set()
        for track in tracks:
            play_params = track.get("attributes", {}).get("playParams", {})
            catalog_id = play_params.get("catalogId")
            if catalog_id:
                ids.add(str(catalog_id))
            track_id = track.get("id")
            if track_id:
                ids.add(str(track_id))
        return ids

    # =========================================================================
    # Library write operations
    # =========================================================================

    def add_songs_to_library(self, catalog_ids: List[str]) -> bool:
        """Add songs to the user's library by catalog IDs. Max 100 per call."""
        if not catalog_ids:
            return True

        for i in range(0, len(catalog_ids), 100):
            batch = catalog_ids[i : i + 100]
            ids_param = "&".join(f"ids[songs]={cid}" for cid in batch)
            url = f"{BASE_URL}/v1/me/library?{ids_param}"
            self._request("POST", url)

        return True

    def add_songs_to_favorites(self, catalog_ids: List[str]) -> bool:
        """Mark songs as favorites (hearted). Separate from library."""
        if not catalog_ids:
            return True

        for i in range(0, len(catalog_ids), 100):
            batch = catalog_ids[i : i + 100]
            ids_param = "&".join(f"ids[songs]={cid}" for cid in batch)
            url = f"{BASE_URL}/v1/me/favorites?{ids_param}"
            try:
                self._request("POST", url)
            except AppleMusicAPIError as e:
                # Favorites endpoint may not be available on all accounts
                logger.warning(f"Failed to favorite songs: {e}")
                return False

        return True

    def add_albums_to_library(self, catalog_ids: List[str]) -> bool:
        """Add albums to the user's library by catalog IDs."""
        if not catalog_ids:
            return True

        for i in range(0, len(catalog_ids), 100):
            batch = catalog_ids[i : i + 100]
            ids_param = "&".join(f"ids[albums]={cid}" for cid in batch)
            url = f"{BASE_URL}/v1/me/library?{ids_param}"
            self._request("POST", url)

        return True

    def add_albums_to_favorites(self, catalog_ids: List[str]) -> bool:
        """Mark albums as favorites (hearted). Separate from library."""
        if not catalog_ids:
            return True

        for i in range(0, len(catalog_ids), 100):
            batch = catalog_ids[i : i + 100]
            ids_param = "&".join(f"ids[albums]={cid}" for cid in batch)
            url = f"{BASE_URL}/v1/me/favorites?{ids_param}"
            try:
                self._request("POST", url)
            except AppleMusicAPIError as e:
                logger.warning(f"Failed to favorite albums: {e}")
                return False

        return True

    def create_playlist(self, name: str, description: str = "") -> Optional[dict]:
        """Create a new library playlist. Returns the playlist data dict."""
        url = f"{BASE_URL}/v1/me/library/playlists"
        payload = {
            "attributes": {"name": name, "description": description},
        }
        data = self._request("POST", url, json=payload)
        items = data.get("data", [])
        return items[0] if items else None

    def add_tracks_to_playlist(self, playlist_id: str, catalog_ids: List[str]) -> bool:
        """Add tracks to a library playlist. Batches in groups of 100."""
        if not catalog_ids:
            return True

        url = f"{BASE_URL}/v1/me/library/playlists/{playlist_id}/tracks"
        for i in range(0, len(catalog_ids), 100):
            batch = catalog_ids[i : i + 100]
            payload = {"data": [{"id": cid, "type": "songs"} for cid in batch]}
            self._request("POST", url, json=payload)

        return True

    def get_or_create_playlist(self, name: str) -> Optional[str]:
        """Find an existing playlist by name, or create one. Returns playlist ID."""
        playlists = self.get_library_playlists()
        for pl in playlists:
            pl_name = pl.get("attributes", {}).get("name", "")
            if pl_name.lower() == name.lower():
                return pl.get("id")

        new_pl = self.create_playlist(name)
        return new_pl.get("id") if new_pl else None

    # =========================================================================
    # Session validation
    # =========================================================================

    def validate_session(self) -> bool:
        """Validate that the session tokens work."""
        try:
            url = f"{BASE_URL}/v1/me/library/playlists?limit=1"
            self._request("GET", url)
            return True
        except (AuthenticationError, AppleMusicAPIError):
            return False


class AppleMusicAPIError(Exception):
    """General Apple Music API error."""

    pass


class AuthenticationError(AppleMusicAPIError):
    """Authentication/token error."""

    pass
