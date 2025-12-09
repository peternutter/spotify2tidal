"""Tests for the library export module."""

import tempfile
import os
from pathlib import Path

import pytest

from spotify2tidal.library import (
    LibraryExporter,
    export_tracks,
    export_albums,
    export_artists,
    export_not_found_tracks,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_track():
    """Sample Spotify track object."""
    return {
        "id": "spotify123",
        "name": "Test Song",
        "artists": [{"name": "Test Artist"}],
        "album": {"name": "Test Album", "id": "album123"},
        "duration_ms": 180000,
        "external_ids": {"isrc": "US1234567890"},
        "external_urls": {"spotify": "https://open.spotify.com/track/spotify123"},
    }


@pytest.fixture
def sample_album():
    """Sample Spotify album object."""
    return {
        "album": {
            "id": "album123",
            "name": "Test Album",
            "artists": [{"name": "Test Artist"}],
            "release_date": "2023-01-15",
            "total_tracks": 10,
            "external_urls": {"spotify": "https://open.spotify.com/album/album123"},
        }
    }


@pytest.fixture
def sample_artist():
    """Sample Spotify artist object."""
    return {
        "id": "artist123",
        "name": "Test Artist",
        "genres": ["rock", "alternative"],
        "external_urls": {"spotify": "https://open.spotify.com/artist/artist123"},
    }


class TestExportTracks:
    """Tests for export_tracks function."""

    def test_export_tracks_creates_csv(self, temp_dir, sample_track):
        """Test that export_tracks creates a CSV file."""
        result = export_tracks([sample_track], temp_dir)
        assert result.exists()
        assert result.suffix == ".csv"

    def test_export_tracks_content(self, temp_dir, sample_track):
        """Test that exported CSV contains correct data."""
        export_tracks([sample_track], temp_dir)
        filepath = temp_dir / "spotify_tracks.csv"
        
        with open(filepath) as f:
            content = f.read()
        
        assert "spotify123" in content
        assert "Test Song" in content
        assert "Test Artist" in content
        assert "Test Album" in content


class TestExportAlbums:
    """Tests for export_albums function."""

    def test_export_albums_creates_csv(self, temp_dir, sample_album):
        """Test that export_albums creates a CSV file."""
        result = export_albums([sample_album], temp_dir)
        assert result.exists()
        assert result.suffix == ".csv"


class TestExportArtists:
    """Tests for export_artists function."""

    def test_export_artists_creates_csv(self, temp_dir, sample_artist):
        """Test that export_artists creates a CSV file."""
        result = export_artists([sample_artist], temp_dir)
        assert result.exists()
        assert result.suffix == ".csv"


class TestExportNotFoundTracks:
    """Tests for export_not_found_tracks function."""

    def test_export_not_found_creates_csv(self, temp_dir, sample_track):
        """Test that not found tracks export creates a CSV file."""
        result = export_not_found_tracks([sample_track], temp_dir)
        assert result.exists()
        assert result.name == "not_found_tracks.csv"


class TestLibraryExporter:
    """Tests for LibraryExporter class."""

    def test_add_tracks(self, temp_dir, sample_track):
        """Test adding tracks to exporter."""
        exporter = LibraryExporter(temp_dir)
        exporter.add_tracks([sample_track])
        assert len(exporter.tracks) == 1

    def test_add_not_found_track(self, temp_dir, sample_track):
        """Test adding not-found track."""
        exporter = LibraryExporter(temp_dir)
        exporter.add_not_found_track(sample_track)
        assert len(exporter.not_found_tracks) == 1

    def test_export_all(self, temp_dir, sample_track, sample_album, sample_artist):
        """Test exporting all collected data."""
        exporter = LibraryExporter(temp_dir)
        exporter.add_tracks([sample_track])
        exporter.add_albums([sample_album])
        exporter.add_artists([sample_artist])
        exporter.add_not_found_track(sample_track)
        
        result = exporter.export_all()
        
        assert "tracks" in result
        assert "albums" in result
        assert "artists" in result
        assert "not_found_tracks" in result

    def test_get_stats(self, temp_dir, sample_track):
        """Test getting statistics."""
        exporter = LibraryExporter(temp_dir)
        exporter.add_tracks([sample_track, sample_track])
        exporter.add_not_found_track(sample_track)
        
        stats = exporter.get_stats()
        
        assert stats["tracks"] == 2
        assert stats["not_found_tracks"] == 1
        assert stats["albums"] == 0
