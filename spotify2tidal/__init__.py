"""
spotify2tidal - Sync your Spotify library to Tidal.

Features:
- Sync playlists (incremental updates)
- Sync liked/saved tracks
- Sync saved albums
- Sync followed artists
- Smart track matching (ISRC, duration, name, artist)
- Caching to avoid redundant API calls
- Async/concurrent for speed
- Progress bars
"""

import logging

from .auth import open_spotify_session, open_tidal_session
from .cache import MatchCache
from .sync import SyncEngine

__all__ = [
    "SyncEngine",
    "MatchCache",
    "open_spotify_session",
    "open_tidal_session",
]

__version__ = "2.0.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
