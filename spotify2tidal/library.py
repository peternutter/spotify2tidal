"""
Library export utilities for saving Spotify library data and not-found items to CSV.
"""

import csv
import datetime
import io
from pathlib import Path
from typing import List, Optional


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


class LibraryExporter:
    """
    Manages exporting library data during sync operations.
    Collects items during sync and exports at the end.
    """

    def __init__(self, export_dir: Optional[Path] = None):
        if export_dir:
            self.export_dir = Path(export_dir)
        else:
            self.export_dir = None  # None indicates in-memory mode

        # Collections to track during sync
        self.tracks: List[dict] = []
        self.albums: List[dict] = []
        self.artists: List[dict] = []
        self.podcasts: List[dict] = []  # Spotify shows/podcasts
        self.not_found_tracks: List[dict] = []
        self.not_found_albums: List[dict] = []
        self.not_found_artists: List[dict] = []

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

    def export_all(self) -> dict:
        """
        Export all collected data to CSV files.

        Returns dict with paths to created files (or file contents if in memory).
        """
        results = {}
        # Mapping of data list -> (export_func, filename_key, default_filename)
        exports = [
            (self.tracks, export_tracks, "tracks", "spotify_tracks.csv"),
            (self.albums, export_albums, "albums", "spotify_albums.csv"),
            (self.artists, export_artists, "artists", "spotify_artists.csv"),
            (self.podcasts, export_podcasts, "podcasts", "spotify_podcasts.csv"),
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
            "not_found_tracks": len(self.not_found_tracks),
            "not_found_albums": len(self.not_found_albums),
            "not_found_artists": len(self.not_found_artists),
        }
