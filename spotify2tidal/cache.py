"""
Caching layer for track matches and search failures.
Uses SQLite for persistence across runs.
"""

import datetime
import sqlite3
from pathlib import Path
from typing import Optional


class MatchCache:
    """
    SQLite-based cache for track/album matches and search failures.
    Persists between runs to avoid redundant API calls.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path.home() / ".spotify2tidal_cache.db"
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS track_matches (
                    spotify_id TEXT PRIMARY KEY,
                    tidal_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS album_matches (
                    spotify_id TEXT PRIMARY KEY,
                    tidal_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artist_matches (
                    spotify_id TEXT PRIMARY KEY,
                    tidal_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_failures (
                    spotify_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    retry_after TIMESTAMP
                )
            """)
            conn.commit()

    def get_track_match(self, spotify_id: str) -> Optional[int]:
        """
        Get cached Tidal track ID for a Spotify track.
        Returns None if not cached, or the cached ID (which may be 0 for failures).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT tidal_id FROM track_matches WHERE spotify_id = ?", (spotify_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def cache_track_match(self, spotify_id: str, tidal_id: int):
        """Cache a successful track match."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO track_matches (spotify_id, tidal_id)
                VALUES (?, ?)
            """,
                (spotify_id, tidal_id),
            )
            conn.commit()

    def get_album_match(self, spotify_id: str) -> Optional[int]:
        """
        Get cached Tidal album ID for a Spotify album.
        Returns None if not cached.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT tidal_id FROM album_matches WHERE spotify_id = ?", (spotify_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def cache_album_match(self, spotify_id: str, tidal_id: int):
        """Cache a successful album match."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO album_matches (spotify_id, tidal_id)
                VALUES (?, ?)
            """,
                (spotify_id, tidal_id),
            )
            conn.commit()

    def get_artist_match(self, spotify_id: str) -> Optional[int]:
        """
        Get cached Tidal artist ID for a Spotify artist.
        Returns None if not cached.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT tidal_id FROM artist_matches WHERE spotify_id = ?",
                (spotify_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def cache_artist_match(self, spotify_id: str, tidal_id: int):
        """Cache a successful artist match."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artist_matches (spotify_id, tidal_id)
                VALUES (?, ?)
            """,
                (spotify_id, tidal_id),
            )
            conn.commit()

    def has_recent_failure(self, spotify_id: str, days: int = 7) -> bool:
        """
        Check if we've recently failed to find this track.
        Uses exponential backoff - failures retry after increasing intervals.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT retry_after FROM search_failures WHERE spotify_id = ?",
                (spotify_id,),
            )
            row = cursor.fetchone()
            if row:
                retry_after = datetime.datetime.fromisoformat(row[0])
                return datetime.datetime.now() < retry_after
            return False

    def cache_failure(self, spotify_id: str):
        """
        Cache a failed search with exponential backoff for retries.
        First failure: retry after 1 day
        Each subsequent: double the interval (up to 30 days max)
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check existing failure
            cursor = conn.execute(
                "SELECT created_at, retry_after FROM search_failures WHERE spotify_id = ?",
                (spotify_id,),
            )
            row = cursor.fetchone()

            now = datetime.datetime.now()

            if row:
                created = datetime.datetime.fromisoformat(row[0])
                # Double the interval
                current_interval = now - created
                new_interval = min(current_interval * 2, datetime.timedelta(days=30))
            else:
                new_interval = datetime.timedelta(days=1)

            retry_after = now + new_interval

            conn.execute(
                """
                INSERT OR REPLACE INTO search_failures
                (spotify_id, created_at, retry_after)
                VALUES (?, ?, ?)
            """,
                (spotify_id, now.isoformat(), retry_after.isoformat()),
            )
            conn.commit()

    def remove_failure(self, spotify_id: str):
        """Remove a failure entry (when track is later found)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM search_failures WHERE spotify_id = ?", (spotify_id,)
            )
            conn.commit()

    def clear_cache(self):
        """Clear all cached data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM track_matches")
            conn.execute("DELETE FROM album_matches")
            conn.execute("DELETE FROM artist_matches")
            conn.execute("DELETE FROM search_failures")
            conn.commit()

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            track_matches = conn.execute(
                "SELECT COUNT(*) FROM track_matches"
            ).fetchone()[0]
            album_matches = conn.execute(
                "SELECT COUNT(*) FROM album_matches"
            ).fetchone()[0]
            artist_matches = conn.execute(
                "SELECT COUNT(*) FROM artist_matches"
            ).fetchone()[0]
            failures = conn.execute("SELECT COUNT(*) FROM search_failures").fetchone()[
                0
            ]
            return {
                "cached_track_matches": track_matches,
                "cached_album_matches": album_matches,
                "cached_artist_matches": artist_matches,
                "cached_failures": failures,
            }
