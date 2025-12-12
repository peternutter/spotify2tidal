"""
Library export utilities for saving Spotify library data and not-found items to CSV.
"""

import csv
import datetime
from pathlib import Path
from typing import List, Optional


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_tracks(
    tracks: List[dict], export_dir: Path, filename: str = "spotify_tracks.csv"
):
    """
    Export Spotify tracks to CSV.

    Args:
        tracks: List of Spotify track objects
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
                    track.get("id", ""),
                    track.get("name", ""),
                    artists,
                    album,
                    track.get("duration_ms", 0),
                    isrc,
                    datetime.datetime.now().isoformat(),
                ]
            )

    return filepath


def export_albums(
    albums: List[dict], export_dir: Path, filename: str = "spotify_albums.csv"
):
    """
    Export Spotify albums to CSV.

    Args:
        albums: List of Spotify album objects (from saved albums endpoint)
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
                    album.get("id", ""),
                    album.get("name", ""),
                    artists,
                    album.get("release_date", ""),
                    album.get("total_tracks", 0),
                    datetime.datetime.now().isoformat(),
                ]
            )

    return filepath


def export_artists(
    artists: List[dict], export_dir: Path, filename: str = "spotify_artists.csv"
):
    """
    Export Spotify artists to CSV.

    Args:
        artists: List of Spotify artist objects
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["spotify_id", "name", "genres", "exported_at"])

        for artist in artists:
            if not artist or not artist.get("id"):
                continue
            genres = ", ".join(artist.get("genres", []))

            writer.writerow(
                [
                    artist.get("id", ""),
                    artist.get("name", ""),
                    genres,
                    datetime.datetime.now().isoformat(),
                ]
            )

    return filepath


def export_podcasts(
    podcasts: List[dict], export_dir: Path, filename: str = "spotify_podcasts.csv"
):
    """
    Export Spotify podcasts/shows to CSV.

    Args:
        podcasts: List of Spotify show objects (from saved shows endpoint)
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
                    show.get("id", ""),
                    show.get("name", ""),
                    show.get("publisher", ""),
                    description,
                    show.get("total_episodes", 0),
                    url,
                    datetime.datetime.now().isoformat(),
                ]
            )

    return filepath


def export_not_found_tracks(
    not_found: List[dict], export_dir: Path, filename: str = "not_found_tracks.csv"
):
    """
    Export tracks that weren't found on Tidal.

    Args:
        not_found: List of Spotify track objects that weren't found
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
                    track.get("id", ""),
                    track.get("name", ""),
                    artists,
                    album,
                    isrc,
                    url,
                    datetime.datetime.now().isoformat(),
                ]
            )

    return filepath


def export_not_found_albums(
    not_found: List[dict], export_dir: Path, filename: str = "not_found_albums.csv"
):
    """
    Export albums that weren't found on Tidal.

    Args:
        not_found: List of Spotify album objects that weren't found
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
                    album.get("id", ""),
                    album.get("name", ""),
                    artists,
                    album.get("release_date", ""),
                    url,
                    datetime.datetime.now().isoformat(),
                ]
            )

    return filepath


def export_not_found_artists(
    not_found: List[dict], export_dir: Path, filename: str = "not_found_artists.csv"
):
    """
    Export artists that weren't found on Tidal.

    Args:
        not_found: List of Spotify artist objects that weren't found
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["spotify_id", "name", "spotify_url", "exported_at"])

        for artist in not_found:
            if not artist or not artist.get("id"):
                continue
            url = artist.get("external_urls", {}).get("spotify", "")

            writer.writerow(
                [
                    artist.get("id", ""),
                    artist.get("name", ""),
                    url,
                    datetime.datetime.now().isoformat(),
                ]
            )

    return filepath


# ============================================================================
# Tidal Library Export Functions
# ============================================================================


def export_tidal_tracks(
    tracks: list, export_dir: Path, filename: str = "tidal_tracks.csv"
):
    """
    Export Tidal favorite tracks to CSV.

    Args:
        tracks: List of tidalapi.Track objects
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
                        track.name or "",
                        artists,
                        album_name,
                        track.duration or 0,
                        isrc,
                        datetime.datetime.now().isoformat(),
                    ]
                )
            except Exception:
                continue

    return filepath


def export_tidal_albums(
    albums: list, export_dir: Path, filename: str = "tidal_albums.csv"
):
    """
    Export Tidal favorite albums to CSV.

    Args:
        albums: List of tidalapi.Album objects
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
                        album.name or "",
                        artists,
                        release_date,
                        album.num_tracks or 0,
                        datetime.datetime.now().isoformat(),
                    ]
                )
            except Exception:
                continue

    return filepath


def export_tidal_artists(
    artists: list, export_dir: Path, filename: str = "tidal_artists.csv"
):
    """
    Export Tidal favorite artists to CSV.

    Args:
        artists: List of tidalapi.Artist objects
        export_dir: Directory to save the CSV
        filename: Output filename
    """
    ensure_dir(export_dir)
    filepath = export_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["tidal_id", "name", "exported_at"])

        for artist in artists:
            if not artist:
                continue
            try:
                writer.writerow(
                    [
                        artist.id,
                        artist.name or "",
                        datetime.datetime.now().isoformat(),
                    ]
                )
            except Exception:
                continue

    return filepath


class LibraryExporter:
    """
    Manages exporting library data during sync operations.
    Collects items during sync and exports at the end.
    """

    def __init__(self, export_dir: Optional[Path] = None):
        self.export_dir = Path(export_dir) if export_dir else Path("./library")

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

        Returns dict with paths to created files.
        """
        results = {}

        if self.tracks:
            results["tracks"] = export_tracks(self.tracks, self.export_dir)

        if self.albums:
            results["albums"] = export_albums(self.albums, self.export_dir)

        if self.artists:
            results["artists"] = export_artists(self.artists, self.export_dir)

        if self.podcasts:
            results["podcasts"] = export_podcasts(self.podcasts, self.export_dir)

        if self.not_found_tracks:
            results["not_found_tracks"] = export_not_found_tracks(
                self.not_found_tracks, self.export_dir
            )

        if self.not_found_albums:
            results["not_found_albums"] = export_not_found_albums(
                self.not_found_albums, self.export_dir
            )

        if self.not_found_artists:
            results["not_found_artists"] = export_not_found_artists(
                self.not_found_artists, self.export_dir
            )

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
