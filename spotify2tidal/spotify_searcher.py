"""
Spotify search with smart matching and caching.

Mirrors TidalSearcher but searches Spotify for Tidal items.
Uses ISRC-first strategy for most reliable matching.
"""

import logging
from typing import Optional

import spotipy

from .cache import MatchCache
from .matching import normalize, simplify
from .rate_limiter import RateLimiter
from .retry_utils import retry_async_call

logger = logging.getLogger(__name__)


class SpotifySearcher:
    """Async Spotify search with smart matching."""

    def __init__(
        self, session: spotipy.Spotify, cache: MatchCache, rate_limiter: RateLimiter
    ):
        self.session = session
        self.cache = cache
        self.rate_limiter = rate_limiter

    async def search_track(self, tidal_track) -> Optional[str]:
        """
        Search for a Tidal track on Spotify, return Spotify track ID if found.

        Uses ISRC-first strategy for most reliable matching.
        """
        tidal_id = tidal_track.id
        if not tidal_id:
            return None

        # Check cache first (reverse lookup)
        cached = self.cache.get_spotify_track_match(tidal_id)
        if cached is not None:
            return cached if cached else None

        # Check if we've failed before
        failure_key = f"tidal:{tidal_id}"
        if self.cache.has_recent_failure(failure_key):
            return None

        # Try ISRC search first (most reliable)
        isrc = getattr(tidal_track, "isrc", None)
        if isrc:
            result = await self._search_by_isrc(isrc, tidal_track)
            if result:
                self.cache.cache_spotify_track_match(tidal_id, result)
                return result

        # Fall back to metadata search
        result = await self._search_by_metadata(tidal_track)
        if result:
            self.cache.cache_spotify_track_match(tidal_id, result)
            return result

        # Cache the failure
        self.cache.cache_failure(failure_key)
        return None

    async def _search_by_isrc(self, isrc: str, tidal_track) -> Optional[str]:
        """Search Spotify by ISRC code."""
        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(
                self.session.search, q=f"isrc:{isrc}", type="track", limit=1
            )

            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                spotify_track = tracks[0]
                # Verify it's available
                if spotify_track.get("is_playable", True):
                    return spotify_track["id"]
        except Exception as e:
            logger.warning(f"ISRC search failed for {isrc}: {e}")
        finally:
            self.rate_limiter.release()

        return None

    async def _search_by_metadata(self, tidal_track) -> Optional[str]:
        """Search by track name and artist."""
        track_name = tidal_track.name
        artists = tidal_track.artists or []
        if not track_name or not artists:
            return None

        artist_name = artists[0].name if artists else ""
        query = f"track:{simplify(track_name)} artist:{simplify(artist_name)}"

        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(
                self.session.search, q=query, type="track", limit=10
            )

            for spotify_track in results.get("tracks", {}).get("items", []):
                if self._tracks_match(spotify_track, tidal_track):
                    return spotify_track["id"]
        except Exception as e:
            logger.warning(f"Metadata search failed: {e}")
        finally:
            self.rate_limiter.release()

        return None

    def _tracks_match(self, spotify_track: dict, tidal_track) -> bool:
        """Check if a Spotify track matches a Tidal track."""
        # Duration check (within 3 seconds)
        spotify_duration = spotify_track.get("duration_ms", 0) / 1000
        tidal_duration = tidal_track.duration or 0
        if abs(spotify_duration - tidal_duration) > 3:
            return False

        # Name check
        spotify_name = spotify_track.get("name", "").lower()
        tidal_name = (tidal_track.name or "").lower()
        simple_spotify = simplify(spotify_name)
        simple_tidal = simplify(tidal_name)

        if simple_tidal not in spotify_name and simple_spotify not in tidal_name:
            # Try normalized comparison
            if normalize(simple_tidal) not in normalize(spotify_name):
                return False

        # Artist check
        spotify_artists = {a["name"].lower() for a in spotify_track.get("artists", [])}
        tidal_artists = {a.name.lower() for a in (tidal_track.artists or [])}

        # At least one artist should match
        if not spotify_artists & tidal_artists:
            # Try normalized
            spotify_normalized = {normalize(a) for a in spotify_artists}
            tidal_normalized = {normalize(a) for a in tidal_artists}
            if not spotify_normalized & tidal_normalized:
                return False

        return True

    async def search_album(self, tidal_album) -> Optional[str]:
        """Search for a Tidal album on Spotify."""
        tidal_id = tidal_album.id
        if not tidal_id:
            return None

        # Check cache first
        cached = self.cache.get_spotify_album_match(tidal_id)
        if cached is not None:
            return cached if cached else None

        name = tidal_album.name
        artists = tidal_album.artists or []
        if not name or not artists:
            return None

        artist_name = artists[0].name if artists else ""
        query = f"album:{simplify(name)} artist:{simplify(artist_name)}"

        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(
                self.session.search, q=query, type="album", limit=10
            )

            for spotify_album in results.get("albums", {}).get("items", []):
                if self._albums_match(spotify_album, tidal_album):
                    self.cache.cache_spotify_album_match(tidal_id, spotify_album["id"])
                    return spotify_album["id"]
        except Exception as e:
            logger.warning(f"Album search failed: {e}")
        finally:
            self.rate_limiter.release()

        return None

    def _albums_match(self, spotify_album: dict, tidal_album) -> bool:
        """Check if a Spotify album matches a Tidal album."""
        spotify_name = simplify(spotify_album.get("name", "")).lower()
        tidal_name = simplify(tidal_album.name or "").lower()

        # Name similarity check
        if spotify_name != tidal_name:
            # Try looser match
            if tidal_name not in spotify_name and spotify_name not in tidal_name:
                return False

        # Artist check
        spotify_artists = {a["name"].lower() for a in spotify_album.get("artists", [])}
        tidal_artists = {a.name.lower() for a in (tidal_album.artists or [])}

        return bool(spotify_artists & tidal_artists)

    async def search_artist(self, tidal_artist) -> Optional[str]:
        """Search for a Tidal artist on Spotify."""
        tidal_id = tidal_artist.id
        name = tidal_artist.name
        if not tidal_id or not name:
            return None

        # Check cache first
        cached = self.cache.get_spotify_artist_match(tidal_id)
        if cached is not None:
            return cached if cached else None

        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(
                self.session.search, q=f"artist:{name}", type="artist", limit=10
            )

            for spotify_artist in results.get("artists", {}).get("items", []):
                spotify_name = spotify_artist.get("name", "")
                if spotify_name.lower() == name.lower():
                    self.cache.cache_spotify_artist_match(
                        tidal_id, spotify_artist["id"]
                    )
                    return spotify_artist["id"]
                if normalize(spotify_name.lower()) == normalize(name.lower()):
                    self.cache.cache_spotify_artist_match(
                        tidal_id, spotify_artist["id"]
                    )
                    return spotify_artist["id"]
        except Exception as e:
            logger.warning(f"Artist search failed: {e}")
        finally:
            self.rate_limiter.release()

        return None
