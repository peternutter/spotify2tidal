"""LibraryExporter for collecting/exporting artifacts during sync."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from .library_csv_common import ensure_dir
from .library_csv_spotify import (
    export_albums,
    export_artists,
    export_not_found_albums,
    export_not_found_artists,
    export_not_found_tracks,
    export_podcasts,
    export_spotify_playlist_items,
    export_spotify_playlists,
    export_tracks,
)
from .library_csv_tidal import (
    export_not_found_tidal_albums,
    export_not_found_tidal_artists,
    export_not_found_tidal_tracks,
    export_tidal_albums,
    export_tidal_artists,
    export_tidal_playlist_items,
    export_tidal_playlists,
    export_tidal_tracks,
)
from .library_opml_spotify import export_podcasts_opml


class LibraryExporter:
    """Collects items during sync and exports them as CSVs."""

    def __init__(self, export_dir: Optional[str | Path] = None):
        if export_dir:
            self.export_dir = Path(export_dir)
            ensure_dir(self.export_dir)
        else:
            self.export_dir = None

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
        self.tracks.extend(tracks)

    def add_albums(self, albums: List[dict]):
        self.albums.extend(albums)

    def add_artists(self, artists: List[dict]):
        self.artists.extend(artists)

    def add_podcasts(self, podcasts: List[dict]):
        self.podcasts.extend(podcasts)

    def add_not_found_track(self, track: dict):
        self.not_found_tracks.append(track)

    def add_not_found_album(self, album: dict):
        self.not_found_albums.append(album)

    def add_not_found_artist(self, artist: dict):
        self.not_found_artists.append(artist)

    # Reverse Sync helpers
    def add_tidal_source_tracks(self, tracks: List[Any]):
        self.tidal_source_tracks.extend(tracks)

    def add_tidal_source_albums(self, albums: List[Any]):
        self.tidal_source_albums.extend(albums)

    def add_tidal_source_artists(self, artists: List[Any]):
        self.tidal_source_artists.extend(artists)

    def add_not_found_tidal_track(self, track: Any):
        self.not_found_tidal_tracks.append(track)

    def add_not_found_tidal_album(self, album: Any):
        self.not_found_tidal_albums.append(album)

    def add_not_found_tidal_artist(self, artist: Any):
        self.not_found_tidal_artists.append(artist)

    # Playlist snapshots
    def add_spotify_playlists(self, playlists: List[dict]):
        self.spotify_playlists.extend(playlists)

    def add_spotify_playlist_items(self, items: List[dict]):
        self.spotify_playlist_items.extend(items)

    def add_tidal_playlists(self, playlists: list):
        self.tidal_playlists.extend(list(playlists))

    def add_tidal_playlist_items(self, items: List[dict]):
        self.tidal_playlist_items.extend(items)

    def export_all(self) -> dict:
        results: dict = {}
        exports = [
            (self.tracks, export_tracks, "tracks", "spotify_tracks.csv"),
            (self.albums, export_albums, "albums", "spotify_albums.csv"),
            (self.artists, export_artists, "artists", "spotify_artists.csv"),
            (self.podcasts, export_podcasts, "podcasts", "spotify_podcasts.csv"),
            (
                self.podcasts,
                export_podcasts_opml,
                "podcasts_opml",
                "spotify_podcasts.opml",
            ),
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
            (
                self.not_found_tidal_albums,
                export_not_found_tidal_albums,
                "not_found_tidal_albums",
                "not_found_tidal_albums.csv",
            ),
            (
                self.not_found_tidal_artists,
                export_not_found_tidal_artists,
                "not_found_tidal_artists",
                "not_found_tidal_artists.csv",
            ),
        ]

        for data, func, key, filename in exports:
            if data:
                results[key] = func(data, self.export_dir, filename)

        return results

    def get_stats(self) -> dict:
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
            "not_found_tidal_albums": len(self.not_found_tidal_albums),
            "not_found_tidal_artists": len(self.not_found_tidal_artists),
        }
