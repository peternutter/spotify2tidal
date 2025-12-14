"""
Async Tidal search with smart matching and caching.
"""

import asyncio
import logging
from typing import Optional

import tidalapi

from .cache import MatchCache
from .matching import TrackMatcher, normalize, simplify
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class TidalSearcher:
    """Async Tidal search with smart matching."""

    def __init__(
        self, session: tidalapi.Session, cache: MatchCache, rate_limiter: RateLimiter
    ):
        self.session = session
        self.cache = cache
        self.rate_limiter = rate_limiter

    async def search_track(self, spotify_track: dict) -> Optional[int]:
        """Search for a Spotify track on Tidal, return Tidal track ID if found."""
        spotify_id = spotify_track.get("id")
        if not spotify_id:
            return None

        # Check cache first
        cached = self.cache.get_track_match(spotify_id)
        if cached is not None:
            return cached if cached > 0 else None

        # Check if we've failed before
        if self.cache.has_recent_failure(spotify_id):
            return None

        # Try album search first (more accurate)
        result = await self._search_by_album(spotify_track)
        if result:
            self.cache.cache_track_match(spotify_id, result)
            return result

        # Fall back to direct track search
        result = await self._search_by_track(spotify_track)
        if result:
            self.cache.cache_track_match(spotify_id, result)
            return result

        # Cache the failure
        self.cache.cache_failure(spotify_id)
        return None

    async def _search_by_album(self, spotify_track: dict) -> Optional[int]:
        """Search by album and track number."""
        album = spotify_track.get("album", {})
        artists = album.get("artists", [])

        if not album.get("name") or not artists:
            return None

        query = f"{simplify(album['name'])} {simplify(artists[0]['name'])}"

        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, query, models=[tidalapi.album.Album]
            )

            for tidal_album in results.get("albums", []):
                if not TrackMatcher.album_match(tidal_album, album):
                    continue

                track_num = spotify_track.get("track_number", 0)
                if tidal_album.num_tracks < track_num:
                    continue

                tracks = await asyncio.to_thread(tidal_album.tracks)
                if len(tracks) >= track_num:
                    track = tracks[track_num - 1]
                    if track.available and TrackMatcher.match(track, spotify_track):
                        return track.id
        except Exception as e:
            logger.warning(f"Album search failed: {e}")

        return None

    async def _search_by_track(self, spotify_track: dict) -> Optional[int]:
        """Direct track search."""
        artists = spotify_track.get("artists", [])
        if not artists:
            return None

        query = f"{simplify(spotify_track['name'])} {simplify(artists[0]['name'])}"

        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, query, models=[tidalapi.media.Track]
            )

            for track in results.get("tracks", []):
                if track.available and TrackMatcher.match(track, spotify_track):
                    return track.id
        except Exception as e:
            logger.warning(f"Track search failed: {e}")

        return None

    async def search_album(self, spotify_album: dict) -> Optional[int]:
        """Search for a Spotify album on Tidal."""
        spotify_id = spotify_album.get("id")
        if not spotify_id:
            return None

        artists = spotify_album.get("artists", [])
        if not artists:
            return None

        # Check cache first - ensures consistent IDs across runs
        cached = self.cache.get_album_match(spotify_id)
        if cached is not None:
            return cached if cached > 0 else None

        query = f"{simplify(spotify_album['name'])} {simplify(artists[0]['name'])}"

        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, query, models=[tidalapi.album.Album]
            )

            for album in results.get("albums", []):
                if TrackMatcher.album_match(album, spotify_album):
                    # Cache the match for future runs
                    self.cache.cache_album_match(spotify_id, album.id)
                    return album.id
        except Exception as e:
            logger.warning(f"Album search failed: {e}")

        return None

    async def search_artist(self, spotify_artist: dict) -> Optional[int]:
        """Search for a Spotify artist on Tidal."""
        spotify_id = spotify_artist.get("id")
        name = spotify_artist.get("name")
        if not spotify_id or not name:
            return None

        # Check cache first - ensures consistent IDs across runs
        cached = self.cache.get_artist_match(spotify_id)
        if cached is not None:
            return cached if cached > 0 else None

        await self.rate_limiter.acquire()
        try:
            results = await asyncio.to_thread(
                self.session.search, name, models=[tidalapi.artist.Artist]
            )

            for artist in results.get("artists", []):
                if artist.name.lower() == name.lower():
                    # Cache the match for future runs
                    self.cache.cache_artist_match(spotify_id, artist.id)
                    return artist.id
                if normalize(artist.name.lower()) == normalize(name.lower()):
                    # Cache the match for future runs
                    self.cache.cache_artist_match(spotify_id, artist.id)
                    return artist.id
        except Exception as e:
            logger.warning(f"Artist search failed: {e}")

        return None
