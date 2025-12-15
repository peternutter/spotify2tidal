import asyncio

from spotify2tidal.fetchers.spotify_fetcher import SpotifyFetcher
from spotify2tidal.fetchers.tidal_fetcher import TidalFetcher


class _PagingSpotify:
    def __init__(self):
        self._next_calls = []

        self._saved_tracks_pages = [
            {
                "items": [
                    {"track": {"id": "t1", "type": "track"}},
                    {"track": None},
                    {"track": {"id": "t2", "type": "track"}},
                ],
                "next": "page2",
            },
            {
                "items": [{"track": {"id": "t3", "type": "track"}}],
                "next": None,
            },
        ]
        self._saved_albums_pages = [{"items": [{"album": {"id": "a1"}}], "next": None}]
        self._followed_artists_pages = [
            {"items": [{"id": "ar1"}, {"id": "ar2"}], "next": None}
        ]
        self._playlist_tracks_pages = [
            {
                "items": [
                    {"track": {"id": "p1", "type": "track"}},
                    {"track": {"id": "ep1", "type": "episode"}},
                    {"track": None},
                    {"track": {"id": "p2", "type": "track"}},
                ],
                "next": None,
            }
        ]

    def current_user_saved_tracks(self):
        return self._saved_tracks_pages[0]

    def current_user_saved_albums(self):
        return self._saved_albums_pages[0]

    def current_user_followed_artists(self):
        return {"artists": self._followed_artists_pages[0]}

    def playlist_tracks(self, _playlist_id):
        return self._playlist_tracks_pages[0]

    def current_user_saved_shows(self):
        raise RuntimeError("not authorized")

    def next(self, results):
        self._next_calls.append(results.get("next"))

        if results is self._saved_tracks_pages[0]:
            return self._saved_tracks_pages[1]
        if results is self._followed_artists_pages[0]:
            return {"artists": self._followed_artists_pages[0]}

        # In tests we only paginate saved tracks.
        return {"items": [], "next": None}


def test_spotify_fetcher_paginates_and_limits_and_skips_non_tracks():
    messages = []

    def cb(msg: str):
        messages.append(msg)

    spotify = _PagingSpotify()
    fetcher = SpotifyFetcher(spotify, progress_callback=cb)

    tracks = asyncio.run(fetcher.get_saved_tracks())
    assert [t["id"] for t in tracks] == ["t1", "t2", "t3"]
    assert any("Fetching saved tracks" in m for m in messages)

    messages.clear()
    limited = asyncio.run(fetcher.get_saved_tracks(limit=2))
    assert [t["id"] for t in limited] == ["t1", "t2"]
    assert any("limited" in m for m in messages)

    playlist_tracks = asyncio.run(fetcher.get_playlist_tracks("pl", limit=10))
    assert [t["id"] for t in playlist_tracks] == ["p1", "p2"]


def test_spotify_fetcher_ids_and_podcast_exception_path():
    spotify = _PagingSpotify()
    fetcher = SpotifyFetcher(spotify)

    track_ids = asyncio.run(fetcher.get_saved_track_ids())
    assert track_ids == {"t1", "t2", "t3"}

    album_ids = asyncio.run(fetcher.get_saved_album_ids())
    assert album_ids == {"a1"}

    artist_ids = asyncio.run(fetcher.get_followed_artist_ids())
    assert artist_ids == {"ar1", "ar2"}

    # Should not raise even if shows endpoint fails.
    shows = asyncio.run(fetcher.get_saved_shows())
    assert shows == []


class _FakeTidalTrack:
    def __init__(self, track_id: int):
        self.id = track_id


class _Favorites:
    def __init__(self, tracks, albums, artists):
        self._tracks = tracks
        self._albums = albums
        self._artists = artists

    def tracks(self, limit=100, offset=0):
        return self._tracks[offset : offset + limit]

    def albums(self, limit=100, offset=0):
        return self._albums[offset : offset + limit]

    def artists(self, limit=100, offset=0):
        return self._artists[offset : offset + limit]


class _TidalUser:
    def __init__(self, favorites):
        self.favorites = favorites


class _Tidal:
    def __init__(self, favorites):
        self.user = _TidalUser(favorites)


class _FakePlaylist:
    def __init__(self, tracks):
        self._tracks = tracks

    def tracks(self, limit=100, offset=0):
        return self._tracks[offset : offset + limit]


def test_tidal_fetcher_paginates_ids_and_limits_tracks():
    messages = []

    def cb(msg: str):
        messages.append(msg)

    tracks = [_FakeTidalTrack(i) for i in range(1, 205)]
    favorites = _Favorites(tracks=tracks, albums=[], artists=[])
    tidal = _Tidal(favorites)

    fetcher = TidalFetcher(tidal, progress_callback=cb)
    ids = asyncio.run(fetcher.get_favorite_track_ids())

    assert ids == set(range(1, 205))
    assert any("Fetching Tidal favorites" in m for m in messages)

    limited_tracks = asyncio.run(fetcher.get_favorite_tracks(limit_total=10))
    assert [t.id for t in limited_tracks] == list(range(1, 11))


def test_tidal_fetcher_playlist_tracks_keeps_order_and_respects_limit():
    playlist = _FakePlaylist(
        [_FakeTidalTrack(1), _FakeTidalTrack(2), _FakeTidalTrack(3)]
    )
    fetcher = TidalFetcher(_Tidal(_Favorites(tracks=[], albums=[], artists=[])))

    all_tracks = asyncio.run(fetcher.get_playlist_tracks(playlist))
    assert [t.id for t in all_tracks] == [1, 2, 3]

    limited = asyncio.run(fetcher.get_playlist_tracks(playlist, limit_total=2))
    assert [t.id for t in limited] == [1, 2]
