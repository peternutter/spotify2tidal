from __future__ import annotations

from pathlib import Path

import pytest

import spotify2tidal.auth as auth


def test_open_spotify_session_requires_credentials(monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)

    with pytest.raises(ValueError):
        auth.open_spotify_session({})


def test_open_spotify_session_uses_env_and_passes_cache_path(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")

    captured = {}

    class _OAuth:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class _Spotify:
        def __init__(self, auth_manager=None):
            self.auth_manager = auth_manager

    monkeypatch.setattr(auth, "SpotifyOAuth", _OAuth)
    monkeypatch.setattr(auth.spotipy, "Spotify", _Spotify)

    cache_path = str(tmp_path / ".spotify_cache")
    spotify = auth.open_spotify_session({}, cache_path=cache_path)

    assert isinstance(spotify, _Spotify)
    assert captured["client_id"] == "id"
    assert captured["client_secret"] == "secret"
    assert captured["cache_path"] == cache_path
    assert captured["open_browser"] is True


def test_open_tidal_session_loads_existing_session_file(monkeypatch, tmp_path: Path):
    session_file = tmp_path / "session.json"
    session_file.write_text("{}")

    calls = {"loaded": 0, "oauth": 0, "saved": 0}

    class _Session:
        def load_session_from_file(self, path: Path):
            assert Path(path) == session_file
            calls["loaded"] += 1

        def check_login(self):
            return True

        def login_oauth(self):
            calls["oauth"] += 1
            raise AssertionError("should not start oauth")

        def save_session_to_file(self, _path: Path):
            calls["saved"] += 1

    monkeypatch.setattr(auth.tidalapi, "Session", _Session)

    session = auth.open_tidal_session({}, session_file=str(session_file))
    assert isinstance(session, _Session)
    assert calls["loaded"] == 1
    assert calls["oauth"] == 0
    assert calls["saved"] == 0


def test_open_tidal_session_runs_oauth_and_saves(monkeypatch, tmp_path: Path):
    session_file = tmp_path / "session.json"

    calls = {"oauth": 0, "saved": 0}

    class _Login:
        verification_uri_complete = "login.tidal.com/device"
        user_code = "ABCD"

    class _Future:
        def result(self):
            return None

    class _Session:
        def __init__(self):
            self._logged_in = False

        def load_session_from_file(self, _path: Path):
            raise AssertionError("should not load missing file")

        def check_login(self):
            return self._logged_in

        def login_oauth(self):
            calls["oauth"] += 1
            self._logged_in = True
            return _Login(), _Future()

        def save_session_to_file(self, path: Path):
            assert Path(path) == session_file
            calls["saved"] += 1

    monkeypatch.setattr(auth.tidalapi, "Session", _Session)
    monkeypatch.setattr(auth.webbrowser, "open", lambda _url: True)

    session = auth.open_tidal_session({}, session_file=str(session_file))
    assert isinstance(session, _Session)
    assert calls["oauth"] == 1
    assert calls["saved"] == 1
