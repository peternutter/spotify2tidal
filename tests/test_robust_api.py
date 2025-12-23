import asyncio
from unittest.mock import MagicMock

import pytest

from spotify2tidal.fetchers.spotify_fetcher import SpotifyFetcher
from spotify2tidal.fetchers.tidal_fetcher import TidalFetcher
from spotify2tidal.retry_utils import retry_async_call


class FlakyClient:
    def __init__(self, success_data, fail_count=1):
        self.success_data = success_data
        self.fail_count = fail_count
        self.attempts = 0

    def call(self, *args, **kwargs):
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise ConnectionResetError("Connection reset by peer")
        return self.success_data


def test_retry_async_call_eventually_succeeds():
    client = FlakyClient(success_data="ok", fail_count=2)

    async def run():
        result = await retry_async_call(client.call)
        assert result == "ok"
        assert client.attempts == 3

    asyncio.run(run())


def test_spotify_fetcher_retries_on_connection_reset():
    # Mock spotipy.Spotify
    mock_spotify = MagicMock()

    # Simulate a flaky 'current_user_saved_tracks'
    flaky = FlakyClient(success_data={"items": [], "next": None}, fail_count=1)
    mock_spotify.current_user_saved_tracks.side_effect = flaky.call

    fetcher = SpotifyFetcher(mock_spotify)

    async def run():
        tracks = await fetcher.get_saved_tracks()
        assert tracks == []
        assert flaky.attempts == 2

    asyncio.run(run())


def test_tidal_fetcher_retries_on_connection_reset():
    # Mock tidalapi.Session
    mock_tidal = MagicMock()

    # Simulate a flaky favorite tracks fetch
    flaky = FlakyClient(success_data=[], fail_count=1)
    mock_tidal.user.favorites.tracks.side_effect = flaky.call

    fetcher = TidalFetcher(mock_tidal)

    async def run():
        tracks = await fetcher.get_favorite_track_ids()
        assert tracks == set()
        assert flaky.attempts == 2

    asyncio.run(run())


def test_retry_async_call_rethrows_after_max_attempts():
    client = FlakyClient(success_data="ok", fail_count=5)  # More than 3

    async def run():
        with pytest.raises(ConnectionResetError):
            await retry_async_call(client.call, max_attempts=3)
        assert client.attempts == 3

    asyncio.run(run())
