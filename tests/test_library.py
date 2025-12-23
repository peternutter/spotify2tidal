"""Tests for the library export module."""

import tempfile
from pathlib import Path

import pytest

from spotify2tidal.library_csv_spotify import (
    export_albums,
    export_artists,
    export_not_found_tracks,
    export_podcasts,
    export_tracks,
)
from spotify2tidal.library_exporter import LibraryExporter
from spotify2tidal.library_opml_spotify import export_podcasts_opml


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


@pytest.fixture
def sample_podcast():
    """Sample Spotify show/podcast object."""
    return {
        "show": {
            "id": "show123",
            "name": "Test Podcast",
            "publisher": "Test Publisher",
            "description": "A test podcast about testing",
            "total_episodes": 50,
            "external_urls": {"spotify": "https://open.spotify.com/show/show123"},
        }
    }


class TestExportPodcasts:
    """Tests for export_podcasts function."""

    def test_export_podcasts_creates_csv(self, temp_dir, sample_podcast):
        """Test that export_podcasts creates a CSV file."""
        result = export_podcasts([sample_podcast], temp_dir)
        assert result.exists()
        assert result.suffix == ".csv"
        assert result.name == "spotify_podcasts.csv"

    def test_export_podcasts_content(self, temp_dir, sample_podcast):
        """Test that exported CSV contains correct data."""
        export_podcasts([sample_podcast], temp_dir)
        filepath = temp_dir / "spotify_podcasts.csv"

        with open(filepath) as f:
            content = f.read()

        assert "show123" in content
        assert "Test Podcast" in content
        assert "Test Publisher" in content


class TestExportPodcastsOPML:
    """Tests for export_podcasts_opml function."""

    def test_export_podcasts_opml_creates_file(self, temp_dir, sample_podcast):
        """Test that export_podcasts_opml creates an OPML file."""
        result = export_podcasts_opml([sample_podcast], temp_dir)
        assert result.exists()
        assert result.suffix == ".opml"
        assert result.name == "spotify_podcasts.opml"

    def test_export_podcasts_opml_content(self, temp_dir, sample_podcast, monkeypatch):
        """Test that exported OPML contains correct data and structure."""
        import requests

        # Mock requests to return something so it doesn't skip the item
        def mock_get(*args, **kwargs):
            class MockResponse:
                def json(self):
                    return {
                        "results": [
                            {"trackName": "Test Podcast", "feedUrl": "https://example.com/rss"}
                        ]
                    }

                def __getattr__(self, name):
                    return 200 if name == "status_code" else None

            return MockResponse()

        monkeypatch.setattr(requests.Session, "get", mock_get)

        export_podcasts_opml([sample_podcast], temp_dir)
        filepath = temp_dir / "spotify_podcasts.opml"

        with open(filepath) as f:
            content = f.read()

        assert '<?xml version="1.0" encoding="utf-8"?>' in content
        assert '<opml version="1.0">' in content
        assert "<outline" in content
        assert 'version="RSS"' in content
        assert 'text="Test Podcast"' in content
        assert 'title="Test Podcast"' in content
        assert 'xmlUrl="https://example.com/rss"' in content

    def test_export_podcasts_opml_resolves_rss(self, temp_dir, sample_podcast, monkeypatch):
        """Test that export_podcasts_opml resolves RSS feeds using the API."""
        import requests

        def mock_get(*args, **kwargs):
            class MockResponse:
                def __init__(self, json_data):
                    self.json_data = json_data
                    self.status_code = 200

                def json(self):
                    return self.json_data

            return MockResponse(
                {"results": [{"trackName": "Test Podcast", "feedUrl": "https://example.com/rss"}]}
            )

        monkeypatch.setattr(requests.Session, "get", mock_get)

        export_podcasts_opml([sample_podcast], temp_dir)
        filepath = temp_dir / "spotify_podcasts.opml"

        with open(filepath) as f:
            content = f.read()

        # The xmlUrl should be the resolved one, not the spotify one
        assert 'xmlUrl="https://example.com/rss"' in content
        assert 'version="RSS"' in content
        # htmlUrl is removed
        assert "https://open.spotify.com/show/show123" not in content


class TestPodcastRobustResolution:
    """Tests for the improved robust podcast resolution logic."""

    def test_normalize(self):
        from spotify2tidal.library_opml_spotify import normalize

        assert normalize("The Daily Podcast") == "thedaily"
        assert normalize("Joe Rogan Experience (Podcast)") == "joeroganexperience"
        assert normalize("News Show") == "news"

    def test_score_match(self):
        from spotify2tidal.library_opml_spotify import score_match

        s_name = "My Cool Podcast"
        s_pub = "Author"

        # Perfect match
        res1 = {"trackName": "My Cool Podcast", "artistName": "Author"}
        assert score_match(s_name, s_pub, res1) >= 1.5

        # Name match, publisher mismatch
        res2 = {"trackName": "My Cool Podcast", "artistName": "Wrong"}
        assert score_match(s_name, s_pub, res2) == 1.0

        # Partial name match
        res3 = {"trackName": "My Cool Podcast Extra", "artistName": "Author"}
        assert score_match(s_name, s_pub, res3) == 1.0  # 0.5 (name contains) + 0.5 (pub match)

    def test_extract_rss_from_description(self):
        from spotify2tidal.library_opml_spotify import extract_rss_from_text

        text = "Visit us at https://example.com/feed.rss for more."
        assert extract_rss_from_text(text) == "https://example.com/feed.rss"

        text2 = "Follow our feed: http://feeds.podcast.com/show"
        assert extract_rss_from_text(text2) == "http://feeds.podcast.com/show"

    def test_resolve_rss_url_desc_priority(self, monkeypatch):
        from spotify2tidal.library_opml_spotify import resolve_rss_url

        # Should return desc link without even calling API
        res = resolve_rss_url(None, "Name", description="RSS: https://site.com/rss")
        assert res == "https://site.com/rss"


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
