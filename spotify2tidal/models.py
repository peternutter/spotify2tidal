"""
Data models for music library items.

Uses dataclasses for clean, minimal definitions with
platform-specific factory methods.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Set


@dataclass
class LibraryItem:
    """Base class for library items (tracks, albums, artists)."""

    name: str
    artists: List[str]
    isrc: Optional[str] = None
    spotify_id: Optional[str] = None
    tidal_id: Optional[int] = None
    added_at: Optional[str] = None
    source: Optional[str] = None
    synced_to: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if self.added_at is None:
            self.added_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "artists": self.artists,
            "isrc": self.isrc,
            "spotify_id": self.spotify_id,
            "tidal_id": self.tidal_id,
            "added_at": self.added_at,
            "source": self.source,
            "synced_to": list(self.synced_to),
        }


@dataclass
class Track(LibraryItem):
    """A track in the library."""

    album: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["album"] = self.album
        data["duration_ms"] = self.duration_ms
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Track":
        """Create from dictionary."""
        track = cls(
            name=data.get("name", ""),
            artists=data.get("artists", []),
            album=data.get("album", ""),
            duration_ms=data.get("duration_ms", 0),
            isrc=data.get("isrc"),
            spotify_id=data.get("spotify_id"),
            tidal_id=data.get("tidal_id"),
            added_at=data.get("added_at"),
            source=data.get("source"),
        )
        track.synced_to = set(data.get("synced_to", []))
        return track

    @classmethod
    def from_spotify(cls, spotify_track: dict) -> "Track":
        """Create Track from Spotify API response."""
        artists = [a["name"] for a in spotify_track.get("artists", [])]
        album = spotify_track.get("album", {}).get("name", "")
        isrc = spotify_track.get("external_ids", {}).get("isrc")

        track = cls(
            name=spotify_track.get("name", ""),
            artists=artists,
            album=album,
            duration_ms=spotify_track.get("duration_ms", 0),
            isrc=isrc,
            spotify_id=spotify_track.get("id"),
            source="spotify",
        )
        track.synced_to.add("spotify")
        return track

    @classmethod
    def from_tidal(cls, tidal_track) -> "Track":
        """Create Track from Tidal API response."""
        artists = [a.name for a in (tidal_track.artists or [])]
        album = tidal_track.album.name if tidal_track.album else ""
        isrc = getattr(tidal_track, "isrc", None) or ""

        track = cls(
            name=tidal_track.name or "",
            artists=artists,
            album=album,
            duration_ms=(tidal_track.duration or 0) * 1000,
            isrc=isrc,
            tidal_id=tidal_track.id,
            source="tidal",
        )
        track.synced_to.add("tidal")
        return track


@dataclass
class Album(LibraryItem):
    """An album in the library."""

    release_date: str = ""
    total_tracks: int = 0

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["release_date"] = self.release_date
        data["total_tracks"] = self.total_tracks
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Album":
        """Create from dictionary."""
        album = cls(
            name=data.get("name", ""),
            artists=data.get("artists", []),
            release_date=data.get("release_date", ""),
            total_tracks=data.get("total_tracks", 0),
            spotify_id=data.get("spotify_id"),
            tidal_id=data.get("tidal_id"),
            added_at=data.get("added_at"),
            source=data.get("source"),
        )
        album.synced_to = set(data.get("synced_to", []))
        return album

    @classmethod
    def from_spotify(cls, spotify_album: dict) -> "Album":
        """Create Album from Spotify API response."""
        # Handle wrapped format (from saved albums endpoint)
        album_data = spotify_album.get("album", spotify_album)
        artists = [a["name"] for a in album_data.get("artists", [])]

        album = cls(
            name=album_data.get("name", ""),
            artists=artists,
            release_date=album_data.get("release_date", ""),
            total_tracks=album_data.get("total_tracks", 0),
            spotify_id=album_data.get("id"),
            source="spotify",
        )
        album.synced_to.add("spotify")
        return album

    @classmethod
    def from_tidal(cls, tidal_album) -> "Album":
        """Create Album from Tidal API response."""
        artists = [a.name for a in (tidal_album.artists or [])]
        release = str(tidal_album.release_date) if tidal_album.release_date else ""

        album = cls(
            name=tidal_album.name or "",
            artists=artists,
            release_date=release,
            total_tracks=tidal_album.num_tracks or 0,
            tidal_id=tidal_album.id,
            source="tidal",
        )
        album.synced_to.add("tidal")
        return album


@dataclass
class Artist(LibraryItem):
    """An artist in the library."""

    genres: List[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        # Artists use their own name as the artist list
        if not self.artists or self.artists == []:
            self.artists = [self.name]

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["genres"] = self.genres
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Artist":
        """Create from dictionary."""
        artist = cls(
            name=data.get("name", ""),
            artists=data.get("artists", []),
            genres=data.get("genres", []),
            spotify_id=data.get("spotify_id"),
            tidal_id=data.get("tidal_id"),
            added_at=data.get("added_at"),
            source=data.get("source"),
        )
        artist.synced_to = set(data.get("synced_to", []))
        return artist

    @classmethod
    def from_spotify(cls, spotify_artist: dict) -> "Artist":
        """Create Artist from Spotify API response."""
        artist = cls(
            name=spotify_artist.get("name", ""),
            artists=[spotify_artist.get("name", "")],
            genres=spotify_artist.get("genres", []),
            spotify_id=spotify_artist.get("id"),
            source="spotify",
        )
        artist.synced_to.add("spotify")
        return artist

    @classmethod
    def from_tidal(cls, tidal_artist) -> "Artist":
        """Create Artist from Tidal API response."""
        artist = cls(
            name=tidal_artist.name or "",
            artists=[tidal_artist.name or ""],
            genres=[],  # Tidal API doesn't expose genres easily
            tidal_id=tidal_artist.id,
            source="tidal",
        )
        artist.synced_to.add("tidal")
        return artist


@dataclass
class DiffResult:
    """Result of comparing library with a platform."""

    new_items: List[Any] = field(default_factory=list)
    missing_items: List[Any] = field(default_factory=list)
    matched_items: List[Any] = field(default_factory=list)

    def __repr__(self):
        return (
            f"DiffResult(new={len(self.new_items)}, "
            f"missing={len(self.missing_items)}, "
            f"matched={len(self.matched_items)})"
        )
