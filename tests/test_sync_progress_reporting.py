import asyncio

import pytest

from spotify2tidal.sync_engine import SyncEngine


@pytest.fixture
def sample_album():
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
    return {
        "id": "artist123",
        "name": "Test Artist",
        "genres": ["rock", "alternative"],
        "external_urls": {"spotify": "https://open.spotify.com/artist/artist123"},
    }


class _FakeFavorites:
    def __init__(self, fail_album=False, fail_artist=False):
        self.fail_album = fail_album
        self.fail_artist = fail_artist
        self.added_albums = []
        self.added_artists = []

    def add_album(self, tidal_id: int):
        if self.fail_album:
            raise RuntimeError("boom album")
        self.added_albums.append(tidal_id)

    def add_artist(self, tidal_id: int):
        if self.fail_artist:
            raise RuntimeError("boom artist")
        self.added_artists.append(tidal_id)


class _FakeUser:
    def __init__(self, favorites: _FakeFavorites):
        self.favorites = favorites


class _FakeTidal:
    def __init__(self, favorites: _FakeFavorites):
        self.user = _FakeUser(favorites)


class _FakeSpotify:
    pass


class _SearcherStub:
    def __init__(self, album_id=1, artist_id=2):
        self._album_id = album_id
        self._artist_id = artist_id

    async def search_album(self, album_data: dict):
        return self._album_id

    async def search_artist(self, artist: dict):
        return self._artist_id


def _no_progress_iter(items, *_args, **_kwargs):
    # Avoid tqdm and avoid emitting update events during tests.
    for item in items:
        yield item


def test_sync_albums_progress_not_matched_when_add_fails(tmp_path, sample_album):
    events = []

    def cb(**kwargs):
        if kwargs.get("event") == "item":
            events.append(kwargs)

    favorites = _FakeFavorites(fail_album=True)
    engine = SyncEngine(
        _FakeSpotify(),
        _FakeTidal(favorites),
        library_dir=str(tmp_path),
        progress_callback=cb,
    )
    engine.searcher = _SearcherStub(album_id=123)
    engine._progress_iter = _no_progress_iter  # type: ignore[assignment]

    async def _saved_albums():
        return [sample_album]

    async def _existing_album_ids():
        return set()

    engine.spotify_fetcher.get_saved_albums = _saved_albums  # type: ignore[assignment]
    engine.tidal_fetcher.get_favorite_album_ids = _existing_album_ids  # type: ignore[assignment]

    added, not_found = asyncio.run(engine.sync_albums())
    assert added == 0
    assert not_found == 0

    assert len(events) == 1
    assert events[0]["matched"] is False
    assert events[0].get("failed") is True


def test_sync_albums_progress_matched_when_already_exists(tmp_path, sample_album):
    events = []

    def cb(**kwargs):
        if kwargs.get("event") == "item":
            events.append(kwargs)

    favorites = _FakeFavorites(fail_album=False)
    engine = SyncEngine(
        _FakeSpotify(),
        _FakeTidal(favorites),
        library_dir=str(tmp_path),
        progress_callback=cb,
    )
    engine.searcher = _SearcherStub(album_id=123)
    engine._progress_iter = _no_progress_iter  # type: ignore[assignment]

    async def _saved_albums():
        return [sample_album]

    async def _existing_album_ids():
        return {123}

    engine.spotify_fetcher.get_saved_albums = _saved_albums  # type: ignore[assignment]
    engine.tidal_fetcher.get_favorite_album_ids = _existing_album_ids  # type: ignore[assignment]

    added, not_found = asyncio.run(engine.sync_albums())
    assert added == 0
    assert not_found == 0

    assert len(events) == 1
    assert events[0]["matched"] is True
    assert "failed" not in events[0]


def test_sync_artists_progress_not_matched_when_add_fails(tmp_path, sample_artist):
    events = []

    def cb(**kwargs):
        if kwargs.get("event") == "item":
            events.append(kwargs)

    favorites = _FakeFavorites(fail_artist=True)
    engine = SyncEngine(
        _FakeSpotify(),
        _FakeTidal(favorites),
        library_dir=str(tmp_path),
        progress_callback=cb,
    )
    engine.searcher = _SearcherStub(artist_id=456)
    engine._progress_iter = _no_progress_iter  # type: ignore[assignment]

    async def _followed_artists():
        return [sample_artist]

    async def _existing_artist_ids():
        return set()

    engine.spotify_fetcher.get_followed_artists = _followed_artists  # type: ignore[assignment]
    engine.tidal_fetcher.get_favorite_artist_ids = _existing_artist_ids  # type: ignore[assignment]

    added, not_found = asyncio.run(engine.sync_artists())
    assert added == 0
    assert not_found == 0

    assert len(events) == 1
    assert events[0]["matched"] is False
    assert events[0].get("failed") is True
