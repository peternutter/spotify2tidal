import asyncio
from unittest.mock import MagicMock

from spotify2tidal.library_exporter import LibraryExporter
from spotify2tidal.sync_engine import SyncEngine


def test_reverse_sync_exports_tracks():
    """Test Tidal->Spotify sync exports source tracks and not-found tracks."""
    # Mock dependencies
    mock_spotify = MagicMock()
    mock_tidal = MagicMock()

    # Setup mock tidal tracks
    mock_track = MagicMock()
    mock_track.id = 123
    mock_track.name = "Test Track"
    mock_track.artists = [MagicMock(name="Test Artist")]
    mock_track.album = MagicMock(name="Test Album")
    mock_track.duration = 180
    mock_track.isrc = "US1234567890"

    # Setup sync engine with library
    engine = SyncEngine(
        spotify=mock_spotify,
        tidal=mock_tidal,
        library_dir="/tmp/test_library",  # will be mocked
    )

    # We'll use a real LibraryExporter but mock the file writing parts if needed,
    # or just inspect the internal lists.
    engine.library = LibraryExporter(None)  # in-memory

    # Mock fetchers
    engine.tidal_fetcher.get_favorite_tracks = MagicMock(return_value=[mock_track])
    # Assume track is NOT in spotify already
    engine.spotify_fetcher.get_saved_track_ids = MagicMock(return_value=set())

    from unittest.mock import patch

    # The fetchers also need to be async-compatible if they are awaited
    async def mock_get_tracks(*args, **kwargs):
        return [mock_track]

    engine.tidal_fetcher.get_favorite_tracks = mock_get_tracks

    async def mock_get_saved_ids(*args, **kwargs):
        return set()

    engine.spotify_fetcher.get_saved_track_ids = mock_get_saved_ids

    # Run sync
    print("Running sync...")

    # We need to patch SpotifySearcher because sync_favorites_to_spotify
    # creates a new instance locally
    with patch("spotify2tidal.spotify_searcher.SpotifySearcher") as MockSearcher:
        mock_searcher_instance = MockSearcher.return_value

        async def mock_search(*args, **kwargs):
            return None

        mock_searcher_instance.search_track = mock_search

        asyncio.run(engine.sync_favorites_to_spotify())

    print(f"Post sync. tracks: {len(engine.library.tidal_source_tracks)}")

    # Verify source tracks were added to library
    assert len(engine.library.tidal_source_tracks) == 1
    assert engine.library.tidal_source_tracks[0].id == 123

    # Verify not found tracks were added to library
    assert len(engine.library.not_found_tidal_tracks) == 1
    assert engine.library.not_found_tidal_tracks[0].id == 123


def test_reverse_sync_exports_albums():
    """Test Tidal->Spotify sync exports source albums and not-found albums."""
    mock_spotify = MagicMock()
    mock_tidal = MagicMock()

    mock_album = MagicMock()
    mock_album.id = 456
    mock_album.name = "Test Album"
    mock_album.artists = [MagicMock(name="Test Artist")]

    engine = SyncEngine(spotify=mock_spotify, tidal=mock_tidal, library_dir=None)
    engine.library = LibraryExporter(None)

    async def mock_get_albums(*args, **kwargs):
        return [mock_album]

    engine.tidal_fetcher.get_favorite_albums = mock_get_albums

    async def mock_get_saved_ids(*args, **kwargs):
        return set()

    engine.spotify_fetcher.get_saved_album_ids = mock_get_saved_ids

    async def mock_search(*args, **kwargs):
        return None

    engine.searcher.search_album = mock_search

    asyncio.run(engine.sync_albums_to_spotify())

    assert len(engine.library.tidal_source_albums) == 1
    assert engine.library.tidal_source_albums[0].id == 456
    assert len(engine.library.not_found_tidal_albums) == 1
    assert engine.library.not_found_tidal_albums[0].id == 456
