"""Spotify-side CSV export functions."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Optional

from .library_csv_common import export_items


def export_tracks(
    tracks: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_tracks.csv",
) -> str | Path:
    """Export Spotify tracks to CSV."""
    return export_items(
        tracks,
        {
            "spotify_id": lambda t: t.get("id", ""),
            "name": lambda t: t.get("name", ""),
            "artists": lambda t: ", ".join(a["name"] for a in t.get("artists", [])),
            "album": lambda t: t.get("album", {}).get("name", ""),
            "duration_ms": lambda t: t.get("duration_ms", 0),
            "isrc": lambda t: t.get("external_ids", {}).get("isrc", ""),
            "exported_at": lambda t: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_albums(
    albums: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_albums.csv",
) -> str | Path:
    """Export Spotify albums to CSV."""

    def get_album(item: dict) -> dict:
        return item.get("album", item)

    return export_items(
        albums,
        {
            "spotify_id": lambda item: get_album(item).get("id", ""),
            "name": lambda item: get_album(item).get("name", ""),
            "artists": lambda item: ", ".join(
                a["name"] for a in get_album(item).get("artists", [])
            ),
            "release_date": lambda item: get_album(item).get("release_date", ""),
            "total_tracks": lambda item: get_album(item).get("total_tracks", 0),
            "exported_at": lambda item: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_artists(
    artists: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_artists.csv",
) -> str | Path:
    """Export Spotify artists to CSV."""
    return export_items(
        artists,
        {
            "spotify_id": lambda a: a.get("id", ""),
            "name": lambda a: a.get("name", ""),
            "genres": lambda a: ", ".join(a.get("genres", [])),
            "exported_at": lambda a: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_podcasts(
    podcasts: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_podcasts.csv",
) -> str | Path:
    """Export Spotify podcasts/shows to CSV."""

    def get_show(item: dict) -> dict:
        return item.get("show", item)

    return export_items(
        podcasts,
        {
            "spotify_id": lambda item: get_show(item).get("id", ""),
            "name": lambda item: get_show(item).get("name", ""),
            "publisher": lambda item: get_show(item).get("publisher", ""),
            "description": lambda item: (get_show(item).get("description", "") or "")[
                :200
            ],
            "total_episodes": lambda item: get_show(item).get("total_episodes", 0),
            "spotify_url": lambda item: get_show(item)
            .get("external_urls", {})
            .get("spotify", ""),
            "exported_at": lambda item: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_spotify_playlists(
    playlists: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_playlists.csv",
) -> str | Path:
    """Export Spotify playlist metadata to CSV."""
    snapshot_at = datetime.datetime.now().isoformat()
    return export_items(
        playlists,
        {
            "spotify_playlist_id": lambda p: p.get("id", ""),
            "name": lambda p: p.get("name", ""),
            "owner_id": lambda p: (p.get("owner") or {}).get("id", ""),
            "public": lambda p: bool(p.get("public", False)),
            "collaborative": lambda p: bool(p.get("collaborative", False)),
            "track_count": lambda p: int((p.get("tracks") or {}).get("total") or 0),
            "snapshot_at": lambda p: snapshot_at,
        },
        export_dir,
        filename,
    )


def export_spotify_playlist_items(
    items: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_playlist_items.csv",
) -> str | Path:
    """Export Spotify playlist tracks (ordered) to CSV."""
    snapshot_at = datetime.datetime.now().isoformat()
    return export_items(
        items,
        {
            "spotify_playlist_id": lambda row: row.get("spotify_playlist_id", ""),
            "playlist_name": lambda row: row.get("playlist_name", ""),
            "position": lambda row: row.get("position", 0),
            "spotify_track_id": lambda row: row.get("spotify_track_id", ""),
            "tidal_track_id": lambda row: row.get("tidal_track_id", ""),
            "name": lambda row: row.get("name", ""),
            "artists": lambda row: row.get("artists", ""),
            "album": lambda row: row.get("album", ""),
            "isrc": lambda row: row.get("isrc", ""),
            "snapshot_at": lambda row: snapshot_at,
        },
        export_dir,
        filename,
    )


def export_not_found_tracks(
    not_found: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tracks.csv",
) -> str | Path:
    """Export tracks that weren't found on Tidal."""
    return export_items(
        not_found,
        {
            "spotify_id": lambda t: t.get("id", ""),
            "name": lambda t: t.get("name", ""),
            "artists": lambda t: ", ".join(a["name"] for a in t.get("artists", [])),
            "album": lambda t: t.get("album", {}).get("name", ""),
            "isrc": lambda t: t.get("external_ids", {}).get("isrc", ""),
            "spotify_url": lambda t: t.get("external_urls", {}).get("spotify", ""),
            "exported_at": lambda t: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_not_found_albums(
    not_found: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "not_found_albums.csv",
) -> str | Path:
    """Export albums that weren't found on Tidal."""

    def get_album(item: dict) -> dict:
        return item.get("album", item)

    return export_items(
        not_found,
        {
            "spotify_id": lambda item: get_album(item).get("id", ""),
            "name": lambda item: get_album(item).get("name", ""),
            "artists": lambda item: ", ".join(
                a["name"] for a in get_album(item).get("artists", [])
            ),
            "release_date": lambda item: get_album(item).get("release_date", ""),
            "spotify_url": lambda item: get_album(item)
            .get("external_urls", {})
            .get("spotify", ""),
            "exported_at": lambda item: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )


def export_not_found_artists(
    not_found: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "not_found_artists.csv",
) -> str | Path:
    """Export artists that weren't found on Tidal."""
    return export_items(
        not_found,
        {
            "spotify_id": lambda a: a.get("id", ""),
            "name": lambda a: a.get("name", ""),
            "spotify_url": lambda a: a.get("external_urls", {}).get("spotify", ""),
            "exported_at": lambda a: datetime.datetime.now().isoformat(),
        },
        export_dir,
        filename,
    )
