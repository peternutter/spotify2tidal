"""
Caching layer for track matches and search failures.
Uses JSON for persistence across runs (optional).
"""

import datetime
import json
from pathlib import Path
from typing import Optional


class MatchCache:
    """
    Cache for track/album/artist matches and search failures.
    Uses JSON file for persistence (optional), dict for runtime storage.

    For CLI: Pass cache_file to persist between runs.
    For webapp: Use without cache_file for in-memory only (no disk writes).
    """

    def __init__(self, cache_file: Optional[str] = None):
        self._cache_file = Path(cache_file) if cache_file else None
        # Forward mappings: Spotify ID -> Tidal ID
        self._track_matches: dict[str, int] = {}
        self._album_matches: dict[str, int] = {}
        self._artist_matches: dict[str, int] = {}
        # Reverse mappings: Tidal ID -> Spotify ID
        self._reverse_track_matches: dict[int, str] = {}
        self._reverse_album_matches: dict[int, str] = {}
        self._reverse_artist_matches: dict[int, str] = {}
        # Failures cache (works for both directions)
        self._failures: dict[str, str] = {}  # id_key -> retry_after ISO string

        # Load from file if it exists
        if self._cache_file and self._cache_file.exists():
            self._load_from_file()

    def _load_from_file(self):
        """Load cache state from JSON file."""
        if not self._cache_file:
            return

        try:
            with open(self._cache_file) as f:
                data = json.load(f)

            self._track_matches = data.get("tracks", {})
            self._album_matches = data.get("albums", {})
            self._artist_matches = data.get("artists", {})
            self._failures = data.get("failures", {})
            # Load reverse mappings if present, otherwise build from forward
            self._reverse_track_matches = {
                int(k): v for k, v in data.get("reverse_tracks", {}).items()
            }
            self._reverse_album_matches = {
                int(k): v for k, v in data.get("reverse_albums", {}).items()
            }
            self._reverse_artist_matches = {
                int(k): v for k, v in data.get("reverse_artists", {}).items()
            }
            # Build reverse from forward if not present
            if not self._reverse_track_matches:
                self._build_reverse_cache()
        except (json.JSONDecodeError, OSError):
            # Invalid or unreadable file, start fresh
            pass

    def save_to_file(self, path: Optional[str] = None):
        """Save cache state to JSON file."""
        target = Path(path) if path else self._cache_file
        if not target:
            return

        data = {
            "tracks": self._track_matches,
            "albums": self._album_matches,
            "artists": self._artist_matches,
            "reverse_tracks": {
                str(k): v for k, v in self._reverse_track_matches.items()
            },
            "reverse_albums": {
                str(k): v for k, v in self._reverse_album_matches.items()
            },
            "reverse_artists": {
                str(k): v for k, v in self._reverse_artist_matches.items()
            },
            "failures": self._failures,
        }

        with open(target, "w") as f:
            json.dump(data, f, indent=2)

    def get_track_match(self, spotify_id: str) -> Optional[int]:
        """Get cached Tidal track ID for a Spotify track."""
        return self._track_matches.get(spotify_id)

    def cache_track_match(self, spotify_id: str, tidal_id: int):
        """Cache a successful track match (both directions)."""
        self._track_matches[spotify_id] = tidal_id
        self._reverse_track_matches[tidal_id] = spotify_id
        self._auto_save()

    def get_album_match(self, spotify_id: str) -> Optional[int]:
        """Get cached Tidal album ID for a Spotify album."""
        return self._album_matches.get(spotify_id)

    def cache_album_match(self, spotify_id: str, tidal_id: int):
        """Cache a successful album match (both directions)."""
        self._album_matches[spotify_id] = tidal_id
        self._reverse_album_matches[tidal_id] = spotify_id
        self._auto_save()

    def get_artist_match(self, spotify_id: str) -> Optional[int]:
        """Get cached Tidal artist ID for a Spotify artist."""
        return self._artist_matches.get(spotify_id)

    def cache_artist_match(self, spotify_id: str, tidal_id: int):
        """Cache a successful artist match (both directions)."""
        self._artist_matches[spotify_id] = tidal_id
        self._reverse_artist_matches[tidal_id] = spotify_id
        self._auto_save()

    # =========================================================================
    # Reverse lookups (Tidal -> Spotify)
    # =========================================================================

    def get_spotify_track_match(self, tidal_id: int) -> Optional[str]:
        """Get cached Spotify track ID for a Tidal track."""
        return self._reverse_track_matches.get(tidal_id)

    def cache_spotify_track_match(self, tidal_id: int, spotify_id: str):
        """Cache a successful Tidal->Spotify track match."""
        self._reverse_track_matches[tidal_id] = spotify_id
        self._track_matches[spotify_id] = tidal_id
        self._auto_save()

    def get_spotify_album_match(self, tidal_id: int) -> Optional[str]:
        """Get cached Spotify album ID for a Tidal album."""
        return self._reverse_album_matches.get(tidal_id)

    def cache_spotify_album_match(self, tidal_id: int, spotify_id: str):
        """Cache a successful Tidal->Spotify album match."""
        self._reverse_album_matches[tidal_id] = spotify_id
        self._album_matches[spotify_id] = tidal_id
        self._auto_save()

    def get_spotify_artist_match(self, tidal_id: int) -> Optional[str]:
        """Get cached Spotify artist ID for a Tidal artist."""
        return self._reverse_artist_matches.get(tidal_id)

    def cache_spotify_artist_match(self, tidal_id: int, spotify_id: str):
        """Cache a successful Tidal->Spotify artist match."""
        self._reverse_artist_matches[tidal_id] = spotify_id
        self._artist_matches[spotify_id] = tidal_id
        self._auto_save()

    def _build_reverse_cache(self):
        """Build reverse mappings from forward mappings."""
        for spotify_id, tidal_id in self._track_matches.items():
            self._reverse_track_matches[tidal_id] = spotify_id
        for spotify_id, tidal_id in self._album_matches.items():
            self._reverse_album_matches[tidal_id] = spotify_id
        for spotify_id, tidal_id in self._artist_matches.items():
            self._reverse_artist_matches[tidal_id] = spotify_id

    def has_recent_failure(self, spotify_id: str, days: int = 7) -> bool:
        """Check if we've recently failed to find this item."""
        retry_after_str = self._failures.get(spotify_id)
        if retry_after_str:
            try:
                retry_after = datetime.datetime.fromisoformat(retry_after_str)
                return datetime.datetime.now() < retry_after
            except ValueError:
                pass
        return False

    def cache_failure(self, spotify_id: str):
        """
        Cache a failed search with exponential backoff for retries.
        First failure: retry after 1 day
        Each subsequent: double the interval (up to 30 days max)
        """
        now = datetime.datetime.now()

        # Check existing failure for backoff
        existing = self._failures.get(spotify_id)
        if existing:
            try:
                old_retry = datetime.datetime.fromisoformat(existing)
                # Double the interval from when we last set it
                interval = now - old_retry
                new_interval = min(abs(interval) * 2, datetime.timedelta(days=30))
            except ValueError:
                new_interval = datetime.timedelta(days=1)
        else:
            new_interval = datetime.timedelta(days=1)

        retry_after = now + new_interval
        self._failures[spotify_id] = retry_after.isoformat()
        self._auto_save()

    def remove_failure(self, spotify_id: str):
        """Remove a failure entry (when item is later found)."""
        if spotify_id in self._failures:
            del self._failures[spotify_id]
            self._auto_save()

    def clear_cache(self):
        """Clear all cached data."""
        self._track_matches.clear()
        self._album_matches.clear()
        self._artist_matches.clear()
        self._reverse_track_matches.clear()
        self._reverse_album_matches.clear()
        self._reverse_artist_matches.clear()
        self._failures.clear()
        self._auto_save()

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cached_track_matches": len(self._track_matches),
            "cached_album_matches": len(self._album_matches),
            "cached_artist_matches": len(self._artist_matches),
            "cached_reverse_track_matches": len(self._reverse_track_matches),
            "cached_failures": len(self._failures),
        }

    def _auto_save(self):
        """Auto-save to file if configured."""
        if self._cache_file:
            self.save_to_file()

    # Export methods for webapp ZIP download
    def to_dict(self) -> dict:
        """Export cache data as a dictionary (for ZIP export)."""
        return {
            "tracks": self._track_matches.copy(),
            "albums": self._album_matches.copy(),
            "artists": self._artist_matches.copy(),
        }

    def load_from_dict(self, data: dict):
        """Load cache data from a dictionary (for ZIP import)."""
        for spotify_id, tidal_id in data.get("tracks", {}).items():
            self._track_matches[spotify_id] = int(tidal_id)
        for spotify_id, tidal_id in data.get("albums", {}).items():
            self._album_matches[spotify_id] = int(tidal_id)
        for spotify_id, tidal_id in data.get("artists", {}).items():
            self._artist_matches[spotify_id] = int(tidal_id)
