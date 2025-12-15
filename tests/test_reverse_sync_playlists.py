import asyncio

from spotify2tidal.sync_engine import SyncEngine


class _FakeTidalTrack:
    def __init__(self, tidal_id: int):
        self.id = tidal_id
        self.name = f"T{tidal_id}"
        self.duration = 100
        self.artists = []


class _FakeTidalPlaylist:
    def __init__(self, name: str, tracks):
        self.name = name
        self._tracks = tracks

    def tracks(self, limit=100, offset=0):
        return self._tracks[offset : offset + limit]


class _FakeTidalUser:
    def __init__(self, playlists):
        self._playlists = playlists

    def playlists(self):
        return list(self._playlists)


class _FakeTidal:
    def __init__(self, playlists):
        self.user = _FakeTidalUser(playlists)


class _FakeSpotify:
    def __init__(self):
        self.created = []
        self.add_calls = []
        self._user = {"id": "me"}
        self._playlists_pages = [
            {
                "items": [],
                "next": None,
            }
        ]
        self._playlist_items = {}

    def current_user(self):
        return self._user

    def current_user_playlists(self):
        return self._playlists_pages[0]

    def next(self, results):
        # Only one page in these tests.
        return {"items": [], "next": None}

    def user_playlist_create(self, user, name, public=False, description=""):
        playlist_id = f"pl_{name}"
        self.created.append((user, name, public, description))
        return {"id": playlist_id}

    def playlist_items(self, playlist_id, fields=None):
        return self._playlist_items.get(playlist_id, {"items": [], "next": None})

    def playlist_add_items(self, playlist_id, items):
        self.add_calls.append((playlist_id, list(items)))


def _no_progress_iter(items, *_args, **_kwargs):
    for item in items:
        yield item


def test_reverse_sync_playlists_creates_and_adds_in_order(tmp_path):
    tidal_playlist = _FakeTidalPlaylist(
        "My Mix",
        [_FakeTidalTrack(1), _FakeTidalTrack(2), _FakeTidalTrack(3)],
    )

    spotify = _FakeSpotify()
    tidal = _FakeTidal([tidal_playlist])

    engine = SyncEngine(spotify, tidal, library_dir=str(tmp_path))
    engine._progress_iter = _no_progress_iter  # type: ignore[assignment]

    # Stub searcher mapping tidal track id -> spotify id.
    async def _search_track(self, track):
        return {1: "s1", 2: "s2", 3: "s3"}[track.id]

    # Patch only the method used by sync_tidal_playlist_to_spotify.
    from spotify2tidal.spotify_searcher import SpotifySearcher

    original = SpotifySearcher.search_track
    SpotifySearcher.search_track = _search_track  # type: ignore[method-assign]
    try:
        results = asyncio.run(engine.sync_all_playlists_to_spotify())
    finally:
        SpotifySearcher.search_track = original  # type: ignore[method-assign]

    assert "My Mix" in results
    assert results["My Mix"]["added"] == 3
    assert results["My Mix"]["not_found"] == 0

    # Playlist created
    assert spotify.created and spotify.created[0][1] == "My Mix"

    # Tracks added in order
    assert spotify.add_calls == [("pl_My Mix", ["s1", "s2", "s3"])]


def test_reverse_sync_playlists_dedupes_existing_tracks(tmp_path):
    tidal_playlist = _FakeTidalPlaylist(
        "My Mix",
        [_FakeTidalTrack(1), _FakeTidalTrack(2), _FakeTidalTrack(3)],
    )

    spotify = _FakeSpotify()
    tidal = _FakeTidal([tidal_playlist])

    engine = SyncEngine(spotify, tidal, library_dir=str(tmp_path))
    engine._progress_iter = _no_progress_iter  # type: ignore[assignment]

    # Pretend playlist exists already.
    spotify._playlists_pages = [
        {
            "items": [{"id": "pl_existing", "name": "My Mix", "owner": {"id": "me"}}],
            "next": None,
        }
    ]

    # Pretend Spotify playlist already contains s2.
    spotify._playlist_items["pl_existing"] = {
        "items": [{"track": {"id": "s2", "type": "track"}}],
        "next": None,
    }

    async def _search_track(self, track):
        return {1: "s1", 2: "s2", 3: "s3"}[track.id]

    from spotify2tidal.spotify_searcher import SpotifySearcher

    original = SpotifySearcher.search_track
    SpotifySearcher.search_track = _search_track  # type: ignore[method-assign]
    try:
        results = asyncio.run(engine.sync_all_playlists_to_spotify())
    finally:
        SpotifySearcher.search_track = original  # type: ignore[method-assign]

    assert results["My Mix"]["added"] == 2
    assert spotify.add_calls == [("pl_existing", ["s1", "s3"])]
