from __future__ import annotations

import sys
from pathlib import Path

import pytest

import spotify2tidal.cli as cli


def test_load_config_missing_file_returns_empty(tmp_path: Path):
    missing = tmp_path / "nope.yml"
    assert cli.load_config(str(missing)) == {}


def test_load_config_reads_yaml(tmp_path: Path):
    p = tmp_path / "config.yml"
    p.write_text("spotify: {client_id: x, client_secret: y}\n")
    cfg = cli.load_config(str(p))
    assert cfg["spotify"]["client_id"] == "x"


def _write_min_config(path: Path, export_dir: Path):
    path.write_text(f"library:\n  export_dir: '{export_dir}'\n")


def test_main_to_spotify_favorites_calls_engine(monkeypatch, tmp_path: Path, capsys):
    # Fake Spotify/Tidal sessions
    class _Spotify:
        def current_user(self):
            return {"id": "me", "display_name": "Me"}

    class _Tidal:
        def check_login(self):
            return True

    monkeypatch.setattr(cli, "open_spotify_session", lambda *_a, **_k: _Spotify())
    monkeypatch.setattr(cli, "open_tidal_session", lambda *_a, **_k: _Tidal())

    calls = {"favorites": 0, "backup": 0}

    class _Library:
        export_dir = str(tmp_path)

    class _Engine:
        def __init__(self, *args, **kwargs):
            self.library = _Library()

        async def sync_favorites_to_spotify(self):
            calls["favorites"] += 1
            return (2, 1)

        async def export_backup(self, categories=None):
            calls["backup"] += 1
            return {"files": {"cache": str(tmp_path / "cache.json")}}

    monkeypatch.setattr(cli, "SyncEngine", _Engine)

    # Provide a config file so main doesn't early-exit for missing custom path
    config_path = tmp_path / "config.yml"
    _write_min_config(config_path, tmp_path)

    # Build args
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "spotify2tidal",
            "--config",
            str(config_path),
            "--to-spotify",
            "--favorites",
            "--limit",
            "3",
            "--no-color",
        ],
    )

    cli.main()

    assert calls["favorites"] == 1
    assert calls["backup"] == 1

    out = capsys.readouterr().out
    assert "Tidal → Spotify" in out
    assert "Sync Complete" in out


def test_main_errors_when_user_config_missing(monkeypatch, tmp_path: Path):
    missing = tmp_path / "missing.yml"
    monkeypatch.setattr(
        sys, "argv", ["spotify2tidal", "--config", str(missing), "--all"]
    )

    with pytest.raises(SystemExit) as e:
        cli.main()

    assert e.value.code == 1


def test_main_warns_on_to_spotify_without_category(monkeypatch, tmp_path: Path, capsys):
    class _Spotify:
        def current_user(self):
            return {"id": "me", "display_name": "Me"}

    class _Tidal:
        def check_login(self):
            return True

    class _Engine:
        def __init__(self, *args, **kwargs):
            self.library = type("L", (), {"export_dir": str(tmp_path)})()

        async def export_backup(self, categories=None):
            raise AssertionError("backup should not run when no results")

    monkeypatch.setattr(cli, "open_spotify_session", lambda *_a, **_k: _Spotify())
    monkeypatch.setattr(cli, "open_tidal_session", lambda *_a, **_k: _Tidal())
    monkeypatch.setattr(cli, "SyncEngine", _Engine)

    config_path = tmp_path / "config.yml"
    _write_min_config(config_path, tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        ["spotify2tidal", "--config", str(config_path), "--to-spotify", "--no-color"],
    )

    cli.main()
    out = capsys.readouterr().out
    assert "Use --to-spotify" in out
