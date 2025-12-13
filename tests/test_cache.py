"""Tests for the caching layer."""

import os
import tempfile

import pytest

from spotify2tidal.cache import MatchCache


@pytest.fixture
def temp_cache():
    """Create a temporary cache for testing (with file persistence)."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        cache_path = f.name
    try:
        cache = MatchCache(cache_file=cache_path)
        yield cache
    finally:
        if os.path.exists(cache_path):
            os.unlink(cache_path)


@pytest.fixture
def memory_cache():
    """Create an in-memory cache (no file persistence)."""
    return MatchCache()


class TestMatchCache:
    """Tests for MatchCache."""

    def test_cache_and_retrieve_track_match(self, temp_cache):
        """Test caching and retrieving a track match."""
        temp_cache.cache_track_match("spotify_123", 456)
        result = temp_cache.get_track_match("spotify_123")
        assert result == 456

    def test_cache_miss_returns_none(self, temp_cache):
        """Test that cache miss returns None."""
        result = temp_cache.get_track_match("nonexistent")
        assert result is None

    def test_cache_failure(self, temp_cache):
        """Test caching and checking failures."""
        temp_cache.cache_failure("failed_track")
        assert temp_cache.has_recent_failure("failed_track") is True

    def test_no_failure_for_uncached(self, temp_cache):
        """Test that uncached track has no failure."""
        assert temp_cache.has_recent_failure("clean_track") is False

    def test_remove_failure(self, temp_cache):
        """Test removing a failure entry."""
        temp_cache.cache_failure("failed_track")
        temp_cache.remove_failure("failed_track")
        assert temp_cache.has_recent_failure("failed_track") is False

    def test_clear_cache(self, temp_cache):
        """Test clearing all cache data."""
        temp_cache.cache_track_match("track1", 111)
        temp_cache.cache_track_match("track2", 222)
        temp_cache.clear_cache()
        assert temp_cache.get_track_match("track1") is None
        assert temp_cache.get_track_match("track2") is None

    def test_get_stats(self, temp_cache):
        """Test getting cache statistics."""
        temp_cache.cache_track_match("track1", 111)
        temp_cache.cache_failure("failed")
        stats = temp_cache.get_stats()
        assert stats["cached_track_matches"] == 1
        assert stats["cached_failures"] == 1

    def test_album_and_artist_matches(self, temp_cache):
        """Test album and artist caching."""
        temp_cache.cache_album_match("album_123", 789)
        temp_cache.cache_artist_match("artist_456", 321)

        assert temp_cache.get_album_match("album_123") == 789
        assert temp_cache.get_artist_match("artist_456") == 321

    def test_persistence_across_reloads(self, temp_cache):
        """Test that cache persists to file and can be reloaded."""
        temp_cache.cache_track_match("track1", 111)
        temp_cache.cache_album_match("album1", 222)
        cache_file = temp_cache._cache_file

        # Create new cache from same file
        reloaded = MatchCache(cache_file=str(cache_file))

        assert reloaded.get_track_match("track1") == 111
        assert reloaded.get_album_match("album1") == 222

    def test_memory_only_mode(self, memory_cache):
        """Test cache works in memory-only mode (no file)."""
        memory_cache.cache_track_match("track1", 111)
        assert memory_cache.get_track_match("track1") == 111
        assert memory_cache._cache_file is None

    def test_to_dict_export(self, temp_cache):
        """Test exporting cache to dictionary."""
        temp_cache.cache_track_match("track1", 111)
        temp_cache.cache_album_match("album1", 222)
        temp_cache.cache_artist_match("artist1", 333)

        data = temp_cache.to_dict()
        assert data["tracks"]["track1"] == 111
        assert data["albums"]["album1"] == 222
        assert data["artists"]["artist1"] == 333

    def test_load_from_dict(self, memory_cache):
        """Test importing cache from dictionary."""
        data = {
            "tracks": {"track1": 111, "track2": 222},
            "albums": {"album1": 333},
            "artists": {"artist1": 444},
        }

        memory_cache.load_from_dict(data)

        assert memory_cache.get_track_match("track1") == 111
        assert memory_cache.get_track_match("track2") == 222
        assert memory_cache.get_album_match("album1") == 333
        assert memory_cache.get_artist_match("artist1") == 444
