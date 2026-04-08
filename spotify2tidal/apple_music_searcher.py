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
            if not self.fallback_client or await self._is_track_available_in_primary(cached):
                return cached
            self.cache.remove_apple_track_match(spotify_id, cached)

        # Check failure cache
        failure_key = f"apple:{spotify_id}"
        if self.cache.has_recent_failure(failure_key):
            return None

        # Track whether we got real search results (vs throttled empty responses)
        got_results = False

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
            result, had_results = await self._search_by_text(spotify_track, client=client)
            if result:
                self.cache.cache_apple_track_match(spotify_id, result)
                return result
            if had_results:
                got_results = True

        # Only cache failure if we actually got search results back
        # (empty results likely means throttling, not a real miss)
        if got_results:
            self.cache.cache_failure(failure_key)
        return None

    async def _is_track_available_in_primary(self, song_id: str) -> bool:
        """Check whether a catalog track ID exists in the primary storefront."""
        primary_song = await retry_async_call(self.client.get_catalog_song, song_id)
        return bool(primary_song)

    async def _is_album_available_in_primary(self, album_id: str) -> bool:
        """Check whether a catalog album ID exists in the primary storefront."""
        primary_album = await retry_async_call(self.client.get_catalog_album, album_id)
        return bool(primary_album)

    async def _validate_catalog_track_id(self, song_id: Optional[str], client: "AppleMusicClient") -> Optional[str]:
        """Ensure a fallback storefront match is available in the primary storefront."""
        if not song_id:
            return None
        if client is self.client or not self.fallback_client:
            return song_id
        if await self._is_track_available_in_primary(song_id):
            return song_id
        logger.debug(
            f"Rejecting fallback-only Apple Music track {song_id}: "
            f"not available in primary storefront {self.client.storefront}"
        )
        return None

    async def _validate_catalog_album_id(
        self, album_id: Optional[str], client: "AppleMusicClient"
    ) -> Optional[str]:
        """Ensure a fallback storefront album is available in the primary storefront."""
        if not album_id:
            return None
        if client is self.client or not self.fallback_client:
            return album_id
        if await self._is_album_available_in_primary(album_id):
            return album_id
        logger.debug(
            f"Rejecting fallback-only Apple Music album {album_id}: "
            f"not available in primary storefront {self.client.storefront}"
        )
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
                validated_id = await self._validate_catalog_track_id(song.get("id"), client)
                if not validated_id:
                    return None
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
                    return validated_id
                # Even if artist doesn't match perfectly, ISRC is very reliable
                # Accept it anyway but log the mismatch
                logger.debug(
                    f"ISRC match with artist mismatch: " f"Spotify={sp_artists} Apple={am_artist}"
                )
                return validated_id
        except Exception as e:
            logger.debug(f"ISRC search failed for {isrc}: {e}")
        finally:
            self.rate_limiter.release()

        return None

    async def _search_by_text(
        self, spotify_track: dict, client: "Optional[AppleMusicClient]" = None
    ) -> tuple[Optional[str], bool]:
        """Fallback text-based search. Returns (match_id, had_results)."""
        client = client or self.client
        artists = spotify_track.get("artists", [])
        if not artists:
            return None, False

        track_name = spotify_track.get("name", "")
        artist_name = artists[0].get("name", "")
        had_results = False

        # Try specific query first: "track artist"
        query = f"{simplify(track_name)} {simplify(artist_name)}"

        await self.rate_limiter.acquire()
        try:
            results = await retry_async_call(client.search_catalog, query, "songs", 15)
            if results:
                had_results = True
            match = await self._find_best_match(results, spotify_track, client)
            if match:
                return match, True
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
                if results:
                    had_results = True
                match = await self._find_best_match(results, spotify_track, client)
                if match:
                    return match, True
            except Exception as e:
                logger.debug(f"Broad search failed for '{track_name}': {e}")
            finally:
                self.rate_limiter.release()

        return None, had_results

    async def _find_best_match(
        self, am_results: list, spotify_track: dict, client: "AppleMusicClient"
    ) -> Optional[str]:
        """Find the best matching Apple Music track from search results."""
        from thefuzz import fuzz

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

            # Name: substring match OR fuzzy ratio >= 85
            name_match = (
                sp_name in am_name or am_name in sp_name or fuzz.ratio(sp_name, am_name) >= 85
            )
            if not name_match:
                continue

            # Artist: substring match OR fuzzy partial ratio >= 85
            artist_match = any(
                a in am_artist or am_artist in a or fuzz.partial_ratio(a, am_artist) >= 85
                for a in sp_artists
            )
            if not artist_match:
                continue

            # Duration within 15 seconds
            if sp_duration and am_duration:
                if abs(sp_duration - am_duration) > 15000:
                    continue

            # Check for version mismatches (remix, live, acoustic, etc.)
            if self._has_version_mismatch(spotify_track.get("name", ""), attrs.get("name", "")):
                continue

            return await self._validate_catalog_track_id(result.get("id"), client)

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
            if not self.fallback_client or await self._is_album_available_in_primary(cached):
                return cached
            self.cache.remove_apple_album_match(spotify_id, cached)

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
                album_id = await self._validate_catalog_album_id(album_id, client)
                if not album_id:
                    continue
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
