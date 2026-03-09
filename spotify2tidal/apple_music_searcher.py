"""
Async Apple Music search with ISRC-first matching and caching.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from .cache import MatchCache
from .matching import normalize, simplify
from .rate_limiter import RateLimiter
from .retry_utils import retry_async_call

if TYPE_CHECKING:
    from .apple_music_client import AppleMusicClient

logger = logging.getLogger(__name__)


class AppleMusicSearcher:
    """Async Apple Music search with ISRC-first matching strategy."""

    def __init__(
        self,
        client: "AppleMusicClient",
        cache: MatchCache,
        rate_limiter: RateLimiter,
        fallback_client: "Optional[AppleMusicClient]" = None,
    ):
        self.client = client
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.fallback_client = fallback_client

    async def search_track(self, spotify_track: dict) -> Optional[str]:
        """Search for a Spotify track on Apple Music. Returns catalog ID or None."""
        spotify_id = spotify_track.get("id")
        if not spotify_id:
            return None

        # Check cache
        cached = self.cache.get_apple_track_match(spotify_id)
        if cached is not None:
            return cached if cached else None

        # Check failure cache
        failure_key = f"apple:{spotify_id}"
        if self.cache.has_recent_failure(failure_key):
            return None

        # Try primary client, then fallback (e.g., different storefront)
        for client in self._clients():
            # Strategy 1: ISRC match (most reliable)
            isrc = spotify_track.get("external_ids", {}).get("isrc")
            if isrc:
                result = await self._search_by_isrc(isrc, spotify_track, client=client)
                if result:
                    self.cache.cache_apple_track_match(spotify_id, result)
                    return result

            # Strategy 2: Text search with matching
            result = await self._search_by_text(spotify_track, client=client)
            if result:
                self.cache.cache_apple_track_match(spotify_id, result)
                return result

        # Cache the failure
        self.cache.cache_failure(failure_key)
        return None

    def _clients(self):
        """Yield primary client, then fallback if available."""
        yield self.client
        if self.fallback_client:
            yield self.fallback_client

    async def _search_by_isrc(
        self, isrc: str, spotify_track: dict, client: "Optional[AppleMusicClient]" = None
    ) -> Optional[str]:
        """Search by ISRC code - primary strategy."""
        client = client or self.client
        await self.rate_limiter.acquire()
        try:
            song = await retry_async_call(client.search_catalog_by_isrc, isrc)
            if song:
                # Verify it's a reasonable match (ISRC should be definitive,
                # but check artist to avoid rare ISRC reuse)
                am_artist = song.get("attributes", {}).get("artistName", "").lower()
                sp_artists = [a["name"].lower() for a in spotify_track.get("artists", [])]
                # Accept if any Spotify artist appears in Apple Music artist string
                if any(
                    normalize(simplify(a)) in normalize(am_artist)
                    or normalize(am_artist) in normalize(simplify(a))
                    for a in sp_artists
                ):
                    return song.get("id")
                # Even if artist doesn't match perfectly, ISRC is very reliable
                # Accept it anyway but log the mismatch
                logger.debug(
                    f"ISRC match with artist mismatch: " f"Spotify={sp_artists} Apple={am_artist}"
                )
                return song.get("id")
        except Exception as e:
            logger.debug(f"ISRC search failed for {isrc}: {e}")
        finally:
            self.rate_limiter.release()

        return None

    async def _search_by_text(
        self, spotify_track: dict, client: "Optional[AppleMusicClient]" = None
    ) -> Optional[str]:
        """Fallback text-based search."""
        client = client or self.client
        artists = spotify_track.get("artists", [])
        if not artists:
            return None

        track_name = spotify_track.get("name", "")
        artist_name = artists[0].get("name", "")

        # Try specific query first: "track artist"
        query = f"{simplify(track_name)} {simplify(artist_name)}"

        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(client.search_catalog, query, "songs", 15)
            match = self._find_best_match(results, spotify_track)
            if match:
                return match
        except Exception as e:
            logger.debug(f"Text search failed for '{query}': {e}")
        finally:
            self.rate_limiter.release()

        # Try broader query: just track name
        if artist_name.lower() not in track_name.lower():
            await self.rate_limiter.acquire()
            try:
                results = await retry_async_call(
                    client.search_catalog, simplify(track_name), "songs", 15
                )
                match = self._find_best_match(results, spotify_track)
                if match:
                    return match
            except Exception as e:
                logger.debug(f"Broad search failed for '{track_name}': {e}")
            finally:
                self.rate_limiter.release()

        return None

    def _find_best_match(self, am_results: list, spotify_track: dict) -> Optional[str]:
        """Find the best matching Apple Music track from search results."""
        sp_name = normalize(simplify(spotify_track.get("name", ""))).lower()
        sp_artists = {
            normalize(simplify(a["name"])).lower() for a in spotify_track.get("artists", [])
        }
        sp_duration = spotify_track.get("duration_ms", 0)

        for result in am_results:
            attrs = result.get("attributes", {})
            am_name = normalize(simplify(attrs.get("name", ""))).lower()
            am_artist = normalize(attrs.get("artistName", "")).lower()
            am_duration = attrs.get("durationInMillis", 0)

            # Name must match
            if sp_name not in am_name and am_name not in sp_name:
                continue

            # At least one artist must match
            artist_match = any(a in am_artist or am_artist in a for a in sp_artists)
            if not artist_match:
                continue

            # Duration within 3 seconds
            if sp_duration and am_duration:
                if abs(sp_duration - am_duration) > 3000:
                    continue

            # Check for version mismatches (remix, live, acoustic, etc.)
            if self._has_version_mismatch(spotify_track.get("name", ""), attrs.get("name", "")):
                continue

            return result.get("id")

        return None

    @staticmethod
    def _has_version_mismatch(name_a: str, name_b: str) -> bool:
        """Check if one track is a remix/live/etc version and the other isn't."""
        patterns = [
            "instrumental",
            "acapella",
            "remix",
            "live",
            "acoustic",
            "radio edit",
        ]
        a_lower = name_a.lower()
        b_lower = name_b.lower()
        for pattern in patterns:
            if (pattern in a_lower) != (pattern in b_lower):
                return True
        return False

    async def search_album(self, spotify_album: dict) -> Optional[str]:
        """Search for a Spotify album on Apple Music. Returns catalog ID or None."""
        spotify_id = spotify_album.get("id")
        if not spotify_id:
            return None

        cached = self.cache.get_apple_album_match(spotify_id)
        if cached is not None:
            return cached if cached else None

        artists = spotify_album.get("artists", [])
        if not artists:
            return None

        album_name = spotify_album.get("name", "")
        artist_name = artists[0].get("name", "")
        query = f"{simplify(album_name)} {simplify(artist_name)}"

        for client in self._clients():
            result = await self._search_album_with_client(
                client, query, album_name, artist_name, spotify_id
            )
            if result:
                return result

        return None

    async def _search_album_with_client(
        self, client, query, album_name, artist_name, spotify_id
    ) -> Optional[str]:
        """Search for an album using a specific client."""
        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(client.search_catalog, query, "albums", 10)
            sp_name = normalize(simplify(album_name)).lower()

            for result in results:
                attrs = result.get("attributes", {})
                am_name = normalize(simplify(attrs.get("name", ""))).lower()
                am_artist = normalize(attrs.get("artistName", "")).lower()

                # Name similarity check
                if sp_name not in am_name and am_name not in sp_name:
                    continue

                # Artist check
                sp_artist = normalize(simplify(artist_name)).lower()
                if sp_artist not in am_artist and am_artist not in sp_artist:
                    continue

                album_id = result.get("id")
                self.cache.cache_apple_album_match(spotify_id, album_id)
                return album_id

        except Exception as e:
            logger.debug(f"Album search failed for '{query}': {e}")
        finally:
            self.rate_limiter.release()

        return None

    async def search_artist(self, spotify_artist: dict) -> Optional[str]:
        """Search for a Spotify artist on Apple Music. Returns catalog ID or None."""
        spotify_id = spotify_artist.get("id")
        name = spotify_artist.get("name")
        if not spotify_id or not name:
            return None

        cached = self.cache.get_apple_artist_match(spotify_id)
        if cached is not None:
            return cached if cached else None

        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(self.client.search_catalog, name, "artists", 10)
            for result in results:
                am_name = result.get("attributes", {}).get("name", "")
                if am_name.lower() == name.lower():
                    artist_id = result.get("id")
                    self.cache.cache_apple_artist_match(spotify_id, artist_id)
                    return artist_id
                if normalize(am_name.lower()) == normalize(name.lower()):
                    artist_id = result.get("id")
                    self.cache.cache_apple_artist_match(spotify_id, artist_id)
                    return artist_id
        except Exception as e:
            logger.debug(f"Artist search failed for '{name}': {e}")
        finally:
            self.rate_limiter.release()

        return None
