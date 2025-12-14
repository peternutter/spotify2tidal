"""
Unified Library - Ground Truth for Multi-Platform Music Sync.

Manages a single source of truth library that tracks music across
Spotify, Tidal, and potentially other platforms. Uses ISRC codes
as the universal identifier to link tracks across platforms.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import Album, Artist, DiffResult, Track


class UnifiedLibrary:
    """
    Ground truth library for multi-platform music sync.

    Stores all music items with platform-specific IDs, enabling
    sync in any direction and tracking what's on each platform.
    """

    VERSION = "1.0"

    def __init__(self, library_dir: Optional[str] = None):
        self.library_dir = Path(library_dir) if library_dir else None
        self._tracks: Dict[str, Track] = {}  # Key: ISRC or generated ID
        self._albums: Dict[str, Album] = {}
        self._artists: Dict[str, Artist] = {}
        self.created_at = datetime.now().isoformat()
        self.last_updated = self.created_at

        # Index for fast lookups
        self._spotify_track_index: Dict[str, str] = {}  # spotify_id -> key
        self._tidal_track_index: Dict[int, str] = {}  # tidal_id -> key
        self._spotify_album_index: Dict[str, str] = {}
        self._tidal_album_index: Dict[int, str] = {}
        self._spotify_artist_index: Dict[str, str] = {}
        self._tidal_artist_index: Dict[int, str] = {}

    def _generate_key(self, item, item_type: str) -> str:
        """Generate a unique key for an item without ISRC."""
        if item.isrc:
            return item.isrc
        # Fall back to name + first artist
        artist = item.artists[0] if item.artists else "unknown"
        return f"{item_type}:{item.name.lower()}:{artist.lower()}"

    # =========================================================================
    # Loading and Saving
    # =========================================================================

    @classmethod
    def load(cls, path: str) -> "UnifiedLibrary":
        """Load library from JSON file."""
        library = cls()
        filepath = Path(path)

        if not filepath.exists():
            return library

        with open(filepath) as f:
            data = json.load(f)

        library.created_at = data.get("created_at", library.created_at)
        library.last_updated = data.get("last_updated", library.last_updated)

        # Load tracks
        for track_data in data.get("tracks", []):
            track = Track.from_dict(track_data)
            key = library._generate_key(track, "track")
            library._tracks[key] = track
            library._index_track(key, track)

        # Load albums
        for album_data in data.get("albums", []):
            album = Album.from_dict(album_data)
            key = library._generate_key(album, "album")
            library._albums[key] = album
            library._index_album(key, album)

        # Load artists
        for artist_data in data.get("artists", []):
            artist = Artist.from_dict(artist_data)
            key = artist.name.lower()
            library._artists[key] = artist
            library._index_artist(key, artist)

        return library

    def save(self, path: Optional[str] = None):
        """Save library to JSON file."""
        filepath = Path(path) if path else self.library_dir / "library.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        self.last_updated = datetime.now().isoformat()

        data = {
            "version": self.VERSION,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "tracks": [t.to_dict() for t in self._tracks.values()],
            "albums": [a.to_dict() for a in self._albums.values()],
            "artists": [a.to_dict() for a in self._artists.values()],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # Indexing
    # =========================================================================

    def _index_track(self, key: str, track: Track):
        """Add track to lookup indexes."""
        if track.spotify_id:
            self._spotify_track_index[track.spotify_id] = key
        if track.tidal_id:
            self._tidal_track_index[track.tidal_id] = key

    def _index_album(self, key: str, album: Album):
        """Add album to lookup indexes."""
        if album.spotify_id:
            self._spotify_album_index[album.spotify_id] = key
        if album.tidal_id:
            self._tidal_album_index[album.tidal_id] = key

    def _index_artist(self, key: str, artist: Artist):
        """Add artist to lookup indexes."""
        if artist.spotify_id:
            self._spotify_artist_index[artist.spotify_id] = key
        if artist.tidal_id:
            self._tidal_artist_index[artist.tidal_id] = key

    # =========================================================================
    # Adding Items
    # =========================================================================

    def add_track(self, track: Track) -> bool:
        """
        Add a track to the library, merging if it already exists.
        Returns True if new, False if merged with existing.
        """
        key = self._generate_key(track, "track")

        # Check if we already have this track (by ISRC or platform ID)
        existing_key = None
        if track.spotify_id and track.spotify_id in self._spotify_track_index:
            existing_key = self._spotify_track_index[track.spotify_id]
        elif track.tidal_id and track.tidal_id in self._tidal_track_index:
            existing_key = self._tidal_track_index[track.tidal_id]
        elif key in self._tracks:
            existing_key = key

        if existing_key:
            # Merge with existing
            existing = self._tracks[existing_key]
            if track.spotify_id and not existing.spotify_id:
                existing.spotify_id = track.spotify_id
                self._spotify_track_index[track.spotify_id] = existing_key
            if track.tidal_id and not existing.tidal_id:
                existing.tidal_id = track.tidal_id
                self._tidal_track_index[track.tidal_id] = existing_key
            if track.isrc and not existing.isrc:
                existing.isrc = track.isrc
            existing.synced_to.update(track.synced_to)
            return False

        # Add new
        self._tracks[key] = track
        self._index_track(key, track)
        return True

    def add_album(self, album: Album) -> bool:
        """Add an album to the library, merging if exists."""
        key = self._generate_key(album, "album")

        existing_key = None
        if album.spotify_id and album.spotify_id in self._spotify_album_index:
            existing_key = self._spotify_album_index[album.spotify_id]
        elif album.tidal_id and album.tidal_id in self._tidal_album_index:
            existing_key = self._tidal_album_index[album.tidal_id]
        elif key in self._albums:
            existing_key = key

        if existing_key:
            existing = self._albums[existing_key]
            if album.spotify_id and not existing.spotify_id:
                existing.spotify_id = album.spotify_id
                self._spotify_album_index[album.spotify_id] = existing_key
            if album.tidal_id and not existing.tidal_id:
                existing.tidal_id = album.tidal_id
                self._tidal_album_index[album.tidal_id] = existing_key
            existing.synced_to.update(album.synced_to)
            return False

        self._albums[key] = album
        self._index_album(key, album)
        return True

    def add_artist(self, artist: Artist) -> bool:
        """Add an artist to the library, merging if exists."""
        key = artist.name.lower()

        if key in self._artists:
            existing = self._artists[key]
            if artist.spotify_id and not existing.spotify_id:
                existing.spotify_id = artist.spotify_id
                self._spotify_artist_index[artist.spotify_id] = key
            if artist.tidal_id and not existing.tidal_id:
                existing.tidal_id = artist.tidal_id
                self._tidal_artist_index[artist.tidal_id] = key
            existing.synced_to.update(artist.synced_to)
            return False

        self._artists[key] = artist
        self._index_artist(key, artist)
        return True

    def add_from_spotify(
        self,
        tracks: List[dict] = None,
        albums: List[dict] = None,
        artists: List[dict] = None,
    ):
        """Add items from Spotify API responses."""
        for track_data in tracks or []:
            if track_data and track_data.get("id"):
                track = Track.from_spotify(track_data)
                self.add_track(track)

        for album_data in albums or []:
            if album_data:
                album = Album.from_spotify(album_data)
                self.add_album(album)

        for artist_data in artists or []:
            if artist_data and artist_data.get("id"):
                artist = Artist.from_spotify(artist_data)
                self.add_artist(artist)

    def add_from_tidal(
        self,
        tracks: list = None,
        albums: list = None,
        artists: list = None,
    ):
        """Add items from Tidal API responses."""
        for tidal_track in tracks or []:
            if tidal_track:
                track = Track.from_tidal(tidal_track)
                self.add_track(track)

        for tidal_album in albums or []:
            if tidal_album:
                album = Album.from_tidal(tidal_album)
                self.add_album(album)

        for tidal_artist in artists or []:
            if tidal_artist:
                artist = Artist.from_tidal(tidal_artist)
                self.add_artist(artist)

    # =========================================================================
    # Querying
    # =========================================================================

    def get_tracks(self) -> List[Track]:
        """Get all tracks."""
        return list(self._tracks.values())

    def get_albums(self) -> List[Album]:
        """Get all albums."""
        return list(self._albums.values())

    def get_artists(self) -> List[Artist]:
        """Get all artists."""
        return list(self._artists.values())

    def get_track_by_spotify_id(self, spotify_id: str) -> Optional[Track]:
        """Look up track by Spotify ID."""
        key = self._spotify_track_index.get(spotify_id)
        return self._tracks.get(key) if key else None

    def get_track_by_tidal_id(self, tidal_id: int) -> Optional[Track]:
        """Look up track by Tidal ID."""
        key = self._tidal_track_index.get(tidal_id)
        return self._tracks.get(key) if key else None

    def get_track_by_isrc(self, isrc: str) -> Optional[Track]:
        """Look up track by ISRC."""
        return self._tracks.get(isrc)

    def get_missing_on_spotify(self) -> List[Track]:
        """Get tracks that have Tidal ID but no Spotify ID."""
        return [t for t in self._tracks.values() if t.tidal_id and not t.spotify_id]

    def get_missing_on_tidal(self) -> List[Track]:
        """Get tracks that have Spotify ID but no Tidal ID."""
        return [t for t in self._tracks.values() if t.spotify_id and not t.tidal_id]

    def get_albums_missing_on_spotify(self) -> List[Album]:
        """Get albums that have Tidal ID but no Spotify ID."""
        return [a for a in self._albums.values() if a.tidal_id and not a.spotify_id]

    def get_albums_missing_on_tidal(self) -> List[Album]:
        """Get albums that have Spotify ID but no Tidal ID."""
        return [a for a in self._albums.values() if a.spotify_id and not a.tidal_id]

    def get_artists_missing_on_spotify(self) -> List[Artist]:
        """Get artists that have Tidal ID but no Spotify ID."""
        return [a for a in self._artists.values() if a.tidal_id and not a.spotify_id]

    def get_artists_missing_on_tidal(self) -> List[Artist]:
        """Get artists that have Spotify ID but no Tidal ID."""
        return [a for a in self._artists.values() if a.spotify_id and not a.tidal_id]

    # =========================================================================
    # Diffing
    # =========================================================================

    def diff_with_spotify_tracks(self, spotify_tracks: List[dict]) -> DiffResult:
        """Compare library with current Spotify tracks."""
        result = DiffResult()
        seen_keys: Set[str] = set()

        for track_data in spotify_tracks:
            if not track_data or not track_data.get("id"):
                continue

            spotify_id = track_data["id"]
            isrc = track_data.get("external_ids", {}).get("isrc")

            existing = None
            if spotify_id in self._spotify_track_index:
                key = self._spotify_track_index[spotify_id]
                existing = self._tracks.get(key)
            elif isrc and isrc in self._tracks:
                existing = self._tracks[isrc]

            if existing:
                result.matched_items.append(existing)
                seen_keys.add(self._generate_key(existing, "track"))
            else:
                result.new_items.append(Track.from_spotify(track_data))

        for key, track in self._tracks.items():
            if key not in seen_keys and track.spotify_id:
                result.missing_items.append(track)

        return result

    def diff_with_tidal_tracks(self, tidal_tracks: list) -> DiffResult:
        """Compare library with current Tidal tracks."""
        result = DiffResult()
        seen_keys: Set[str] = set()

        for tidal_track in tidal_tracks:
            if not tidal_track:
                continue

            tidal_id = tidal_track.id
            isrc = getattr(tidal_track, "isrc", None)

            existing = None
            if tidal_id in self._tidal_track_index:
                key = self._tidal_track_index[tidal_id]
                existing = self._tracks.get(key)
            elif isrc and isrc in self._tracks:
                existing = self._tracks[isrc]

            if existing:
                result.matched_items.append(existing)
                seen_keys.add(self._generate_key(existing, "track"))
            else:
                result.new_items.append(Track.from_tidal(tidal_track))

        for key, track in self._tracks.items():
            if key not in seen_keys and track.tidal_id:
                result.missing_items.append(track)

        return result

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict:
        """Get library statistics."""
        tracks = list(self._tracks.values())
        albums = list(self._albums.values())
        artists = list(self._artists.values())

        return {
            "total_tracks": len(tracks),
            "total_albums": len(albums),
            "total_artists": len(artists),
            "tracks_on_spotify": sum(1 for t in tracks if t.spotify_id),
            "tracks_on_tidal": sum(1 for t in tracks if t.tidal_id),
            "tracks_on_both": sum(1 for t in tracks if t.spotify_id and t.tidal_id),
            "tracks_missing_spotify": sum(
                1 for t in tracks if t.tidal_id and not t.spotify_id
            ),
            "tracks_missing_tidal": sum(
                1 for t in tracks if t.spotify_id and not t.tidal_id
            ),
            "albums_on_spotify": sum(1 for a in albums if a.spotify_id),
            "albums_on_tidal": sum(1 for a in albums if a.tidal_id),
            "artists_on_spotify": sum(1 for a in artists if a.spotify_id),
            "artists_on_tidal": sum(1 for a in artists if a.tidal_id),
        }

    # =========================================================================
    # Migration from CSV
    # =========================================================================

    def import_from_spotify_csv(self, csv_path: str):
        """Import tracks from existing Spotify CSV export."""
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                artists = [a.strip() for a in row.get("artists", "").split(",")]
                track = Track(
                    name=row.get("name", ""),
                    artists=artists,
                    album=row.get("album", ""),
                    duration_ms=int(row.get("duration_ms", 0)),
                    isrc=row.get("isrc") or None,
                    spotify_id=row.get("spotify_id") or None,
                    source="spotify",
                )
                track.synced_to.add("spotify")
                self.add_track(track)

    def import_from_tidal_csv(self, csv_path: str):
        """Import tracks from existing Tidal CSV export."""
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                artists = [a.strip() for a in row.get("artists", "").split(",")]
                tidal_id = row.get("tidal_id")
                track = Track(
                    name=row.get("name", ""),
                    artists=artists,
                    album=row.get("album", ""),
                    duration_ms=int(row.get("duration_seconds", 0)) * 1000,
                    isrc=row.get("isrc") or None,
                    tidal_id=int(tidal_id) if tidal_id else None,
                    source="tidal",
                )
                track.synced_to.add("tidal")
                self.add_track(track)
