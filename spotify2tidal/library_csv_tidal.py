"""Tidal-side CSV export functions."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from .library_csv_common import export_items


def export_tidal_tracks(
    tracks: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_tracks.csv",
) -> str | Path:
    """Export Tidal favorite tracks to CSV."""
    return export_items(
        tracks,
        {
            "tidal_id": lambda t: getattr(t, "id", ""),
            "name": lambda t: getattr(t, "name", "") or "",
            "artists": lambda t: ", ".join(
                a.name for a in (getattr(t, "artists", None) or [])
            ),
            "album": lambda t: (
                getattr(getattr(t, "album", None), "name", "")
                if getattr(t, "album", None)
                else ""
            ),
            "duration_seconds": lambda t: getattr(t, "duration", 0) or 0,
            "isrc": lambda t: getattr(t, "isrc", "") or "",
            "exported_at": lambda t: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_tidal_albums(
    albums: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_albums.csv",
) -> str | Path:
    """Export Tidal favorite albums to CSV."""
    return export_items(
        albums,
        {
            "tidal_id": lambda a: getattr(a, "id", ""),
            "name": lambda a: getattr(a, "name", "") or "",
            "artists": lambda a: ", ".join(
                ar.name for ar in (getattr(a, "artists", None) or [])
            ),
            "release_date": lambda a: str(getattr(a, "release_date", "")) or "",
            "num_tracks": lambda a: getattr(a, "num_tracks", 0) or 0,
            "exported_at": lambda a: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_tidal_artists(
    artists: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_artists.csv",
) -> str | Path:
    """Export Tidal favorite artists to CSV."""
    return export_items(
        artists,
        {
            "tidal_id": lambda a: getattr(a, "id", ""),
            "name": lambda a: getattr(a, "name", "") or "",
            "exported_at": lambda a: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_tidal_playlists(
    playlists: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_playlists.csv",
) -> str | Path:
    """Export Tidal playlist metadata to CSV."""
    snapshot_at = datetime.datetime.now().isoformat()
    return export_items(
        playlists,
        {
            "tidal_playlist_id": lambda p: getattr(p, "id", ""),
            "name": lambda p: getattr(p, "name", "") or "",
            "track_count": lambda p: int(getattr(p, "num_tracks", 0) or 0),
            "snapshot_at": lambda p: snapshot_at,
        },
        export_dir,
        filename,
    )


def export_tidal_playlist_items(
    items: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_playlist_items.csv",
) -> str | Path:
    """Export Tidal playlist tracks (ordered) to CSV."""
    snapshot_at = datetime.datetime.now().isoformat()
    return export_items(
        items,
        {
            "tidal_playlist_id": lambda row: row.get("tidal_playlist_id", ""),
            "playlist_name": lambda row: row.get("playlist_name", ""),
            "position": lambda row: row.get("position", 0),
            "tidal_track_id": lambda row: row.get("tidal_track_id", ""),
            "spotify_track_id": lambda row: row.get("spotify_track_id", ""),
            "name": lambda row: row.get("name", ""),
            "artists": lambda row: row.get("artists", ""),
            "album": lambda row: row.get("album", ""),
            "isrc": lambda row: row.get("isrc", ""),
            "snapshot_at": lambda row: snapshot_at,
        },
        export_dir,
        filename,
    )


def export_not_found_tidal_tracks(
    not_found: list,
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tidal_tracks.csv",
) -> str | Path:
    """Export Tidal tracks that weren't found on Spotify."""
    return export_items(
        not_found,
        {
            "tidal_id": lambda r: r.get("tidal_id", "")
            if isinstance(r, dict)
            else getattr(r, "id", ""),
            "name": lambda r: r.get("name", "")
            if isinstance(r, dict)
            else (getattr(r, "name", "") or ""),
            "artists": lambda r: (
                r.get("artists", "")
                if isinstance(r, dict)
                else ", ".join(a.name for a in (getattr(r, "artists", None) or []))
            ),
            "album": lambda r: (
                r.get("album", "")
                if isinstance(r, dict)
                else (
                    getattr(getattr(r, "album", None), "name", "")
                    if getattr(r, "album", None)
                    else ""
                )
            ),
            "duration_seconds": lambda r: r.get(
                "duration", r.get("duration_seconds", 0)
            )
            if isinstance(r, dict)
            else (getattr(r, "duration", 0) or 0),
            "isrc": lambda r: r.get("isrc", "")
            if isinstance(r, dict)
            else (getattr(r, "isrc", "") or ""),
            "context": lambda r: r.get("context", "") if isinstance(r, dict) else "",
            "exported_at": lambda r: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_not_found_tidal_albums(
    not_found: list,
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tidal_albums.csv",
) -> str | Path:
    """Export Tidal albums that weren't found on Spotify."""
    return export_items(
        not_found,
        {
            "tidal_id": lambda r: r.get("tidal_id", "")
            if isinstance(r, dict)
            else getattr(r, "id", ""),
            "name": lambda r: r.get("name", "")
            if isinstance(r, dict)
            else (getattr(r, "name", "") or ""),
            "artists": lambda r: (
                r.get("artists", "")
                if isinstance(r, dict)
                else ", ".join(a.name for a in (getattr(r, "artists", None) or []))
            ),
            "exported_at": lambda r: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_not_found_tidal_artists(
    not_found: list,
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tidal_artists.csv",
) -> str | Path:
    """Export Tidal artists that weren't found on Spotify."""
    return export_items(
        not_found,
        {
            "tidal_id": lambda r: r.get("tidal_id", "")
            if isinstance(r, dict)
            else getattr(r, "id", ""),
            "name": lambda r: r.get("name", "")
            if isinstance(r, dict)
            else (getattr(r, "name", "") or ""),
            "exported_at": lambda r: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )
