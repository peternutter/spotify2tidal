"""Tests for the track matching logic."""

import pytest

from spotify2tidal.sync import TrackMatcher, normalize, simplify


class TestNormalize:
    """Tests for normalize function."""

    def test_normalize_ascii(self):
        """ASCII stays the same."""
        assert normalize("hello") == "hello"

    def test_normalize_accents(self):
        """Accented characters become ASCII."""
        assert normalize("café") == "cafe"
        assert normalize("naïve") == "naive"

    def test_normalize_umlauts(self):
        """German umlauts become ASCII."""
        assert normalize("Motörhead") == "Motorhead"


class TestSimplify:
    """Tests for simplify function."""

    def test_simplify_parentheses(self):
        """Remove parenthetical content."""
        assert simplify("Song Name (Remastered)") == "Song Name"
        assert simplify("Track (feat. Artist)") == "Track"

    def test_simplify_brackets(self):
        """Remove bracketed content."""
        assert simplify("Song [Live]") == "Song"

    def test_simplify_dashes(self):
        """Remove content after dash."""
        assert simplify("Song - Radio Edit") == "Song"


class TestTrackMatcher:
    """Tests for TrackMatcher class."""

    def test_duration_match_exact(self):
        """Exact duration matches."""
        class FakeTrack:
            duration = 180
        
        spotify_track = {"duration_ms": 180000}
        assert TrackMatcher.duration_match(FakeTrack(), spotify_track) is True

    def test_duration_match_within_tolerance(self):
        """Duration within 2 second tolerance matches."""
        class FakeTrack:
            duration = 180
        
        spotify_track = {"duration_ms": 181500}  # 1.5 seconds difference
        assert TrackMatcher.duration_match(FakeTrack(), spotify_track) is True

    def test_duration_mismatch(self):
        """Duration outside tolerance doesn't match."""
        class FakeTrack:
            duration = 180
        
        spotify_track = {"duration_ms": 185000}  # 5 seconds difference
        assert TrackMatcher.duration_match(FakeTrack(), spotify_track) is False
