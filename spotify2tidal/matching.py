"""
Track matching utilities for comparing Spotify and Tidal tracks.
"""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    import tidalapi


def normalize(s: str) -> str:
    """Normalize unicode characters to ASCII."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def simplify(text: str) -> str:
    """Simplify track/album name by removing version info in brackets/parentheses."""
    return text.split("-")[0].strip().split("(")[0].strip().split("[")[0].strip()


class TrackMatcher:
    """Smart track matching with multiple strategies."""

    @staticmethod
    def isrc_match(tidal_track: "tidalapi.Track", spotify_track: dict) -> bool:
        """Match by ISRC (International Standard Recording Code) - most reliable."""
        if "isrc" in spotify_track.get("external_ids", {}):
            return tidal_track.isrc == spotify_track["external_ids"]["isrc"]
        return False

    @staticmethod
    def duration_match(
        tidal_track: "tidalapi.Track", spotify_track: dict, tolerance: int = 2
    ) -> bool:
        """Check if durations match within tolerance (seconds)."""
        tidal_duration = tidal_track.duration
        spotify_duration = spotify_track.get("duration_ms", 0) / 1000
        return abs(tidal_duration - spotify_duration) < tolerance

    @staticmethod
    def name_match(tidal_track: "tidalapi.Track", spotify_track: dict) -> bool:
        """Check if track names match, handling various edge cases."""

        def has_pattern(name: str, pattern: str) -> bool:
            return pattern in name.lower()

        # Exclusion rules - if one has it and the other doesn't, it's not a match
        patterns = [
            "instrumental",
            "acapella",
            "remix",
            "live",
            "acoustic",
            "radio edit",
        ]
        tidal_name = tidal_track.name.lower()
        tidal_version = (tidal_track.version or "").lower()
        spotify_name = spotify_track["name"].lower()

        for pattern in patterns:
            tidal_has = has_pattern(tidal_name, pattern) or has_pattern(
                tidal_version, pattern
            )
            spotify_has = has_pattern(spotify_name, pattern)
            if tidal_has != spotify_has:
                return False

        # Simplified name comparison
        simple_spotify = simplify(spotify_name).split("feat.")[0].strip()
        return simple_spotify in tidal_name or normalize(simple_spotify) in normalize(
            tidal_name
        )

    @staticmethod
    def artist_match(tidal_item, spotify_item: dict) -> bool:
        """Check if at least one artist matches between Tidal and Spotify."""

        def split_artists(name: str) -> Set[str]:
            parts = []
            for sep in ["&", ",", "/"]:
                if sep in name:
                    parts.extend(name.split(sep))
                    break
            else:
                parts = [name]
            return {simplify(p.strip().lower()) for p in parts}

        def get_tidal_artists(item, do_normalize: bool = False) -> Set[str]:
            result = set()
            for artist in item.artists:
                name = normalize(artist.name) if do_normalize else artist.name
                result.update(split_artists(name))
            return result

        def get_spotify_artists(item: dict, do_normalize: bool = False) -> Set[str]:
            result = set()
            for artist in item.get("artists", []):
                name = normalize(artist["name"]) if do_normalize else artist["name"]
                result.update(split_artists(name))
            return result

        # Try un-normalized first, then normalized
        if get_tidal_artists(tidal_item) & get_spotify_artists(spotify_item):
            return True
        return bool(
            get_tidal_artists(tidal_item, True)
            & get_spotify_artists(spotify_item, True)
        )

    @classmethod
    def match(cls, tidal_track: "tidalapi.Track", spotify_track: dict) -> bool:
        """Full match check using all strategies."""
        if not spotify_track.get("id"):
            return False

        # ISRC is the most reliable - if it matches, we're done
        if cls.isrc_match(tidal_track, spotify_track):
            return True

        # Otherwise, use combination of duration, name, and artist
        return (
            cls.duration_match(tidal_track, spotify_track)
            and cls.name_match(tidal_track, spotify_track)
            and cls.artist_match(tidal_track, spotify_track)
        )

    @classmethod
    def album_match(
        cls, tidal_album: tidalapi.Album, spotify_album: dict, threshold: float = 0.6
    ) -> bool:
        """Check if albums match by name similarity and artist."""
        name_similarity = SequenceMatcher(
            None,
            simplify(spotify_album["name"]).lower(),
            simplify(tidal_album.name).lower(),
        ).ratio()
        return name_similarity >= threshold and cls.artist_match(
            tidal_album, spotify_album
        )
