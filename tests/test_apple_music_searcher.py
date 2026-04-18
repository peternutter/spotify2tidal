import asyncio

from spotify2tidal.apple_music_searcher import AppleMusicSearcher
from spotify2tidal.cache import MatchCache
from spotify2tidal.rate_limiter import RateLimiter


class _Client:
    def __init__(self, storefront: str, isrc_result=None, catalog_song=None):
        self.storefront = storefront
        self._isrc_result = isrc_result
        self._catalog_song = catalog_song

    def search_catalog_by_isrc(self, _isrc: str):
        return self._isrc_result

    def search_catalog(self, *_args, **_kwargs):
        return []

    def get_catalog_song(self, _song_id: str):
        if isinstance(self._catalog_song, dict):
            return self._catalog_song.get(_song_id)
        return self._catalog_song

    def get_catalog_album(self, _album_id: str):
        return None


def test_search_track_rejects_fallback_only_catalog_match():
    primary = _Client(storefront="cz", isrc_result=None, catalog_song=None)
    fallback = _Client(
        storefront="us",
        isrc_result={"id": "us-only-song", "attributes": {"artistName": "Test Artist"}},
        catalog_song=None,
    )
    searcher = AppleMusicSearcher(
        client=primary,
        cache=MatchCache(),
        rate_limiter=RateLimiter(max_concurrent=1, rate_per_second=0),
        fallback_client=fallback,
    )

    spotify_track = {
        "id": "spotify-track-1",
        "name": "Test Song",
        "artists": [{"name": "Test Artist"}],
        "external_ids": {"isrc": "TEST12345678"},
        "duration_ms": 180000,
    }

    result = asyncio.run(searcher.search_track(spotify_track))

    assert result is None
    assert searcher.cache.get_apple_track_match("spotify-track-1") is None


def test_search_track_drops_stale_cached_id_and_refinds_primary_match():
    cache = MatchCache()
    cache.cache_apple_track_match("spotify-track-2", "stale-us-id")

    primary = _Client(
        storefront="cz",
        isrc_result={"id": "cz-song-id", "attributes": {"artistName": "Test Artist"}},
        catalog_song={"stale-us-id": None, "cz-song-id": {"id": "cz-song-id"}},
    )
    fallback = _Client(storefront="us", isrc_result=None, catalog_song=None)
    searcher = AppleMusicSearcher(
        client=primary,
        cache=cache,
        rate_limiter=RateLimiter(max_concurrent=1, rate_per_second=0),
        fallback_client=fallback,
    )

    spotify_track = {
        "id": "spotify-track-2",
        "name": "Test Song",
        "artists": [{"name": "Test Artist"}],
        "external_ids": {"isrc": "TEST12345679"},
        "duration_ms": 180000,
    }

    result = asyncio.run(searcher.search_track(spotify_track))

    assert result == "cz-song-id"
    assert searcher.cache.get_apple_track_match("spotify-track-2") == "cz-song-id"
