"""
Library export utilities for saving Spotify library data and not-found items to CSV.
"""

import csv
import datetime
import io
from pathlib import Path
from typing import Any, List, Optional


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_csv_cell(value):
    """
    Mitigate CSV/Excel formula injection.

    If a cell begins with one of Excel's formula trigger characters, prefix with a
    single quote so it is treated as literal text.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        return value

    # Leading whitespace can still be interpreted by some spreadsheet apps.
    stripped = value.lstrip()
    if stripped and stripped[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def export_tracks(
    tracks: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_tracks.csv",
) -> str | Path:
    """
    Export Spotify tracks to CSV.
    If export_dir is None, returns the CSV content as a string.
    Otherwise, writes to file and returns the path.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "spotify_id",
            "name",
            "artists",
            "album",
            "duration_ms",
            "isrc",
            "exported_at",
        ]
    )

    for track in tracks:
        if not track or not track.get("id"):
            continue
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        album = track.get("album", {}).get("name", "")
        isrc = track.get("external_ids", {}).get("isrc", "")

        writer.writerow(
            [
                _sanitize_csv_cell(track.get("id", "")),
                _sanitize_csv_cell(track.get("name", "")),
                _sanitize_csv_cell(artists),
                _sanitize_csv_cell(album),
                track.get("duration_ms", 0),
                _sanitize_csv_cell(isrc),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_albums(
    albums: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_albums.csv",
) -> str | Path:
    """
    Export Spotify albums to CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "spotify_id",
            "name",
            "artists",
            "release_date",
            "total_tracks",
            "exported_at",
        ]
    )

    for item in albums:
        album = item.get("album", item)  # Handle both wrapped and unwrapped
        if not album or not album.get("id"):
            continue
        artists = ", ".join(a["name"] for a in album.get("artists", []))

        writer.writerow(
            [
                _sanitize_csv_cell(album.get("id", "")),
                _sanitize_csv_cell(album.get("name", "")),
                _sanitize_csv_cell(artists),
                _sanitize_csv_cell(album.get("release_date", "")),
                album.get("total_tracks", 0),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_artists(
    artists: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_artists.csv",
) -> str | Path:
    """
    Export Spotify artists to CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["spotify_id", "name", "genres", "exported_at"])

    for artist in artists:
        if not artist or not artist.get("id"):
            continue
        genres = ", ".join(artist.get("genres", []))

        writer.writerow(
            [
                _sanitize_csv_cell(artist.get("id", "")),
                _sanitize_csv_cell(artist.get("name", "")),
                _sanitize_csv_cell(genres),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_podcasts(
    podcasts: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_podcasts.csv",
) -> str | Path:
    """
    Export Spotify podcasts/shows to CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "spotify_id",
            "name",
            "publisher",
            "description",
            "total_episodes",
            "spotify_url",
            "exported_at",
        ]
    )

    for item in podcasts:
        show = item.get("show", item)  # Handle both wrapped and unwrapped
        if not show or not show.get("id"):
            continue
        url = show.get("external_urls", {}).get("spotify", "")
        description = (show.get("description", "") or "")[
            :200
        ]  # Truncate long descriptions

        writer.writerow(
            [
                _sanitize_csv_cell(show.get("id", "")),
                _sanitize_csv_cell(show.get("name", "")),
                _sanitize_csv_cell(show.get("publisher", "")),
                _sanitize_csv_cell(description),
                show.get("total_episodes", 0),
                _sanitize_csv_cell(url),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_spotify_playlists(
    playlists: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_playlists.csv",
) -> str | Path:
    """Export Spotify playlist metadata to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "spotify_playlist_id",
            "name",
            "owner_id",
            "public",
            "collaborative",
            "track_count",
            "snapshot_at",
        ]
    )

    snapshot_at = datetime.datetime.now().isoformat()
    for playlist in playlists:
        if not playlist or not playlist.get("id"):
            continue
        tracks = playlist.get("tracks") or {}
        writer.writerow(
            [
                _sanitize_csv_cell(playlist.get("id", "")),
                _sanitize_csv_cell(playlist.get("name", "")),
                _sanitize_csv_cell((playlist.get("owner") or {}).get("id", "")),
                bool(playlist.get("public", False)),
                bool(playlist.get("collaborative", False)),
                int(tracks.get("total") or 0),
                snapshot_at,
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_spotify_playlist_items(
    items: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_playlist_items.csv",
) -> str | Path:
    """Export Spotify playlist tracks (ordered) to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "spotify_playlist_id",
            "playlist_name",
            "position",
            "spotify_track_id",
            "tidal_track_id",
            "name",
            "artists",
            "album",
            "isrc",
            "snapshot_at",
        ]
    )

    snapshot_at = datetime.datetime.now().isoformat()
    for row in items:
        writer.writerow(
            [
                _sanitize_csv_cell(row.get("spotify_playlist_id", "")),
                _sanitize_csv_cell(row.get("playlist_name", "")),
                row.get("position", 0),
                _sanitize_csv_cell(row.get("spotify_track_id", "")),
                _sanitize_csv_cell(row.get("tidal_track_id", "")),
                _sanitize_csv_cell(row.get("name", "")),
                _sanitize_csv_cell(row.get("artists", "")),
                _sanitize_csv_cell(row.get("album", "")),
                _sanitize_csv_cell(row.get("isrc", "")),
                snapshot_at,
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_not_found_tracks(
    not_found: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tracks.csv",
) -> str | Path:
    """Export tracks that weren't found on Tidal."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "spotify_id",
            "name",
            "artists",
            "album",
            "isrc",
            "spotify_url",
            "exported_at",
        ]
    )

    for track in not_found:
        if not track or not track.get("id"):
            continue
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        album = track.get("album", {}).get("name", "")
        isrc = track.get("external_ids", {}).get("isrc", "")
        url = track.get("external_urls", {}).get("spotify", "")

        writer.writerow(
            [
                _sanitize_csv_cell(track.get("id", "")),
                _sanitize_csv_cell(track.get("name", "")),
                _sanitize_csv_cell(artists),
                _sanitize_csv_cell(album),
                _sanitize_csv_cell(isrc),
                _sanitize_csv_cell(url),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_not_found_albums(
    not_found: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "not_found_albums.csv",
) -> str | Path:
    """Export albums that weren't found on Tidal."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "spotify_id",
            "name",
            "artists",
            "release_date",
            "spotify_url",
            "exported_at",
        ]
    )

    for item in not_found:
        album = item.get("album", item)
        if not album or not album.get("id"):
            continue
        artists = ", ".join(a["name"] for a in album.get("artists", []))
        url = album.get("external_urls", {}).get("spotify", "")

        writer.writerow(
            [
                _sanitize_csv_cell(album.get("id", "")),
                _sanitize_csv_cell(album.get("name", "")),
                _sanitize_csv_cell(artists),
                _sanitize_csv_cell(album.get("release_date", "")),
                _sanitize_csv_cell(url),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_not_found_artists(
    not_found: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "not_found_artists.csv",
) -> str | Path:
    """Export artists that weren't found on Tidal."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["spotify_id", "name", "spotify_url", "exported_at"])

    for artist in not_found:
        if not artist or not artist.get("id"):
            continue
        url = artist.get("external_urls", {}).get("spotify", "")

        writer.writerow(
            [
                _sanitize_csv_cell(artist.get("id", "")),
                _sanitize_csv_cell(artist.get("name", "")),
                _sanitize_csv_cell(url),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


# ============================================================================
# Tidal Library Export Functions
# ============================================================================


def export_tidal_tracks(
    tracks: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_tracks.csv",
) -> str | Path:
    """
    Export Tidal favorite tracks to CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tidal_id",
            "name",
            "artists",
            "album",
            "duration_seconds",
            "isrc",
            "exported_at",
        ]
    )

    for track in tracks:
        if not track:
            continue
        try:
            artists = ", ".join(a.name for a in (track.artists or []))
            album_name = track.album.name if track.album else ""
            isrc = getattr(track, "isrc", "") or ""

            writer.writerow(
                [
                    track.id,
                    _sanitize_csv_cell(track.name or ""),
                    _sanitize_csv_cell(artists),
                    _sanitize_csv_cell(album_name),
                    track.duration or 0,
                    _sanitize_csv_cell(isrc),
                    datetime.datetime.now().isoformat(),
                ]
            )
        except Exception:
            continue

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_tidal_albums(
    albums: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_albums.csv",
) -> str | Path:
    """
    Export Tidal favorite albums to CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["tidal_id", "name", "artists", "release_date", "num_tracks", "exported_at"]
    )

    for album in albums:
        if not album:
            continue
        try:
            artists = ", ".join(a.name for a in (album.artists or []))
            release_date = str(album.release_date) if album.release_date else ""

            writer.writerow(
                [
                    album.id,
                    _sanitize_csv_cell(album.name or ""),
                    _sanitize_csv_cell(artists),
                    _sanitize_csv_cell(release_date),
                    album.num_tracks or 0,
                    datetime.datetime.now().isoformat(),
                ]
            )
        except Exception:
            continue

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_tidal_artists(
    artists: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_artists.csv",
) -> str | Path:
    """
    Export Tidal favorite artists to CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["tidal_id", "name", "exported_at"])

    for artist in artists:
        if not artist:
            continue
        try:
            writer.writerow(
                [
                    artist.id,
                    _sanitize_csv_cell(artist.name or ""),
                    datetime.datetime.now().isoformat(),
                ]
            )
        except Exception:
            continue

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_tidal_playlists(
    playlists: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_playlists.csv",
) -> str | Path:
    """Export Tidal playlist metadata to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tidal_playlist_id",
            "name",
            "track_count",
            "snapshot_at",
        ]
    )

    snapshot_at = datetime.datetime.now().isoformat()
    for playlist in playlists:
        if not playlist:
            continue
        try:
            writer.writerow(
                [
                    playlist.id,
                    _sanitize_csv_cell(getattr(playlist, "name", "") or ""),
                    int(getattr(playlist, "num_tracks", 0) or 0),
                    snapshot_at,
                ]
            )
        except Exception:
            continue

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_tidal_playlist_items(
    items: list,
    export_dir: Optional[Path] = None,
    filename: str = "tidal_playlist_items.csv",
) -> str | Path:
    """Export Tidal playlist tracks (ordered) to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tidal_playlist_id",
            "playlist_name",
            "position",
            "tidal_track_id",
            "spotify_track_id",
            "name",
            "artists",
            "album",
            "isrc",
            "snapshot_at",
        ]
    )

    snapshot_at = datetime.datetime.now().isoformat()
    for row in items:
        writer.writerow(
            [
                _sanitize_csv_cell(row.get("tidal_playlist_id", "")),
                _sanitize_csv_cell(row.get("playlist_name", "")),
                row.get("position", 0),
                _sanitize_csv_cell(row.get("tidal_track_id", "")),
                _sanitize_csv_cell(row.get("spotify_track_id", "")),
                _sanitize_csv_cell(row.get("name", "")),
                _sanitize_csv_cell(row.get("artists", "")),
                _sanitize_csv_cell(row.get("album", "")),
                _sanitize_csv_cell(row.get("isrc", "")),
                snapshot_at,
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_not_found_tidal_tracks(
    not_found: list,
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tidal_tracks.csv",
) -> str | Path:
    """Export Tidal tracks that weren't found on Spotify.

    Reverse sync not-found items may be recorded either as:
    - a dict (from playlist sync, with optional context)
    - a tidalapi.Track-like object (from favorites/albums/artists sync)
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tidal_id",
            "name",
            "artists",
            "album",
            "duration_seconds",
            "isrc",
            "context",
            "exported_at",
        ]
    )

    for row in not_found:
        if not row:
            continue

        if isinstance(row, dict):
            tidal_id = row.get("tidal_id", "")
            name = row.get("name", "")
            artists = row.get("artists", "")
            album = row.get("album", "")
            duration = row.get("duration", row.get("duration_seconds", 0))
            isrc = row.get("isrc", "")
            context = row.get("context", "")
        else:
            tidal_id = getattr(row, "id", "")
            name = getattr(row, "name", "") or ""
            duration = getattr(row, "duration", 0) or 0
            isrc = getattr(row, "isrc", "") or ""

            artists_value = getattr(row, "artists", None) or []
            try:
                artists = ", ".join(a.name for a in artists_value)
            except Exception:
                artists = ""

            album_obj = getattr(row, "album", None)
            album = getattr(album_obj, "name", "") if album_obj else ""
            context = ""

        writer.writerow(
            [
                _sanitize_csv_cell(tidal_id),
                _sanitize_csv_cell(name),
                _sanitize_csv_cell(artists),
                _sanitize_csv_cell(album),
                duration,
                _sanitize_csv_cell(isrc),
                _sanitize_csv_cell(context),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_not_found_tidal_albums(
    not_found: list,
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tidal_albums.csv",
) -> str | Path:
    """Export Tidal albums that weren't found on Spotify."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tidal_id",
            "name",
            "artists",
            "exported_at",
        ]
    )

    for row in not_found:
        if not row:
            continue
        if isinstance(row, dict):
            tidal_id = row.get("tidal_id", "")
            name = row.get("name", "")
            artists = row.get("artists", "")
        else:
            tidal_id = getattr(row, "id", "")
            name = getattr(row, "name", "") or ""
            artists_value = getattr(row, "artists", None) or []
            try:
                artists = ", ".join(a.name for a in artists_value)
            except Exception:
                artists = ""

        writer.writerow(
            [
                _sanitize_csv_cell(tidal_id),
                _sanitize_csv_cell(name),
                _sanitize_csv_cell(artists),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


def export_not_found_tidal_artists(
    not_found: list,
    export_dir: Optional[Path] = None,
    filename: str = "not_found_tidal_artists.csv",
) -> str | Path:
    """Export Tidal artists that weren't found on Spotify."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tidal_id",
            "name",
            "exported_at",
        ]
    )

    for row in not_found:
        if not row:
            continue
        if isinstance(row, dict):
            tidal_id = row.get("tidal_id", "")
            name = row.get("name", "")
        else:
            tidal_id = getattr(row, "id", "")
            name = getattr(row, "name", "") or ""

        writer.writerow(
            [
                _sanitize_csv_cell(tidal_id),
                _sanitize_csv_cell(name),
                datetime.datetime.now().isoformat(),
            ]
        )

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath
    return content


class LibraryExporter:
    """
    Manages exporting library data during sync operations.
    Collects items during sync and exports at the end.
    """

    def __init__(self, export_dir: Optional[Path] = None):
        if export_dir:
            self.export_dir = Path(export_dir)
            ensure_dir(self.export_dir)
        else:
            self.export_dir = None  # None indicates in-memory mode

        # Spotify -> Tidal (Forward Sync)
        self.tracks: List[dict] = []
        self.albums: List[dict] = []
        self.artists: List[dict] = []
        self.podcasts: List[dict] = []
        self.not_found_tracks: List[dict] = []
        self.not_found_albums: List[dict] = []
        self.not_found_artists: List[dict] = []

        # Tidal -> Spotify (Reverse Sync)
        self.tidal_source_tracks: List[Any] = []
        self.tidal_source_albums: List[Any] = []
        self.tidal_source_artists: List[Any] = []
        self.not_found_tidal_tracks: List[Any] = []
        self.not_found_tidal_albums: List[Any] = []
        self.not_found_tidal_artists: List[Any] = []

        # Playlist snapshots (normalized)
        self.spotify_playlists: List[dict] = []
        self.spotify_playlist_items: List[dict] = []
        self.tidal_playlists: list = []
        self.tidal_playlist_items: List[dict] = []

    def add_tracks(self, tracks: List[dict]):
        """Add tracks from a sync operation."""
        self.tracks.extend(tracks)

    def add_albums(self, albums: List[dict]):
        """Add albums from a sync operation."""
        self.albums.extend(albums)

    def add_artists(self, artists: List[dict]):
        """Add artists from a sync operation."""
        self.artists.extend(artists)

    def add_podcasts(self, podcasts: List[dict]):
        """Add podcasts/shows from Spotify."""
        self.podcasts.extend(podcasts)

    def add_not_found_track(self, track: dict):
        """Record a track that wasn't found on Tidal."""
        self.not_found_tracks.append(track)

    def add_not_found_album(self, album: dict):
        """Record an album that wasn't found on Tidal."""
        self.not_found_albums.append(album)

    def add_not_found_artist(self, artist: dict):
        """Record an artist that wasn't found on Tidal."""
        self.not_found_artists.append(artist)

    # Tidal -> Spotify helpers (Reverse Sync)
    def add_tidal_source_tracks(self, tracks: List[Any]):
        """Add Tidal source tracks from a reverse sync."""
        self.tidal_source_tracks.extend(tracks)

    def add_tidal_source_albums(self, albums: List[Any]):
        """Add Tidal source albums from a reverse sync."""
        self.tidal_source_albums.extend(albums)

    def add_tidal_source_artists(self, artists: List[Any]):
        """Add Tidal source artists from a reverse sync."""
        self.tidal_source_artists.extend(artists)

    def add_not_found_tidal_track(self, track: Any):
        """Record a Tidal track that wasn't found on Spotify."""
        self.not_found_tidal_tracks.append(track)

    def add_not_found_tidal_album(self, album: Any):
        """Record a Tidal album that wasn't found on Spotify."""
        self.not_found_tidal_albums.append(album)

    def add_not_found_tidal_artist(self, artist: Any):
        """Record a Tidal artist that wasn't found on Spotify."""
        self.not_found_tidal_artists.append(artist)

    def add_spotify_playlists(self, playlists: List[dict]):
        """Add Spotify playlist metadata snapshot."""
        self.spotify_playlists.extend(playlists)

    def add_spotify_playlist_items(self, items: List[dict]):
        """Add Spotify playlist item snapshot rows."""
        self.spotify_playlist_items.extend(items)

    def add_tidal_playlists(self, playlists: list):
        """Add Tidal playlist metadata snapshot."""
        self.tidal_playlists.extend(list(playlists))

    def add_tidal_playlist_items(self, items: List[dict]):
        """Add Tidal playlist item snapshot rows."""
        self.tidal_playlist_items.extend(items)

    def export_all(self) -> dict:
        """
        Export all collected data to CSV files.

        Returns dict with paths to created files (or file contents if in memory).
        """
        results = {}
        # Mapping of data list -> (export_func, filename_key, default_filename)
        exports = [
            # Spotify to Tidal (Forward Sync) exports
            (self.tracks, export_tracks, "tracks", "spotify_tracks.csv"),
            (self.albums, export_albums, "albums", "spotify_albums.csv"),
            (self.artists, export_artists, "artists", "spotify_artists.csv"),
            (self.podcasts, export_podcasts, "podcasts", "spotify_podcasts.csv"),
            (
                self.spotify_playlists,
                export_spotify_playlists,
                "spotify_playlists",
                "spotify_playlists.csv",
            ),
            (
                self.spotify_playlist_items,
                export_spotify_playlist_items,
                "spotify_playlist_items",
                "spotify_playlist_items.csv",
            ),
            (
                self.not_found_tracks,
                export_not_found_tracks,
                "not_found_tracks",
                "not_found_tracks.csv",
            ),
            (
                self.not_found_albums,
                export_not_found_albums,
                "not_found_albums",
                "not_found_albums.csv",
            ),
            (
                self.not_found_artists,
                export_not_found_artists,
                "not_found_artists",
                "not_found_artists.csv",
            ),
            # Tidal to Spotify (Reverse Sync) exports
            (
                self.tidal_source_tracks,
                export_tidal_tracks,
                "tidal_source_tracks",
                "tidal_source_tracks.csv",
            ),
            (
                self.tidal_source_albums,
                export_tidal_albums,
                "tidal_source_albums",
                "tidal_source_albums.csv",
            ),
            (
                self.tidal_source_artists,
                export_tidal_artists,
                "tidal_source_artists",
                "tidal_source_artists.csv",
            ),
            (
                self.tidal_playlists,
                export_tidal_playlists,
                "tidal_playlists",
                "tidal_playlists.csv",
            ),
            (
                self.tidal_playlist_items,
                export_tidal_playlist_items,
                "tidal_playlist_items",
                "tidal_playlist_items.csv",
            ),
            (
                self.not_found_tidal_tracks,
                export_not_found_tidal_tracks,
                "not_found_tidal_tracks",
                "not_found_tidal_tracks.csv",
            ),
        ]

        for data, func, key, filename in exports:
            if data:
                # If export_dir is None, func returns string content
                # If export_dir is set, func writes file and returns Path
                results[key] = func(data, self.export_dir, filename)

        return results

    def get_stats(self) -> dict:
        """Get statistics about collected data."""
        return {
            "tracks": len(self.tracks),
            "albums": len(self.albums),
            "artists": len(self.artists),
            "podcasts": len(self.podcasts),
            "spotify_playlists": len(self.spotify_playlists),
            "spotify_playlist_items": len(self.spotify_playlist_items),
            "tidal_playlists": len(self.tidal_playlists),
            "tidal_playlist_items": len(self.tidal_playlist_items),
            "not_found_tracks": len(self.not_found_tracks),
            "not_found_albums": len(self.not_found_albums),
            "not_found_artists": len(self.not_found_artists),
            "not_found_tidal_tracks": len(self.not_found_tidal_tracks),
        }
