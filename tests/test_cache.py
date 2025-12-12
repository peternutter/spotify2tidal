"""Tests for the caching layer."""

import os
import tempfile

import pytest

from spotify2tidal.cache import MatchCache


@pytest.fixture
def temp_cache():
    """Create a temporary cache for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cache = MatchCache(db_path)
        yield cache
    finally:
        os.unlink(db_path)


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
        assert stats["cached_matches"] == 1
        assert stats["cached_failures"] == 1
