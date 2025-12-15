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

from .cache import MatchCache
from .sync_engine import SyncEngine

try:
    from .auth import open_spotify_session, open_tidal_session
except ModuleNotFoundError:  # pragma: no cover
    # Allow importing the package in minimal environments (e.g., during tests)
    # without optional API client dependencies installed.
    def open_spotify_session(*_args, **_kwargs):  # type: ignore[no-redef]
        raise ModuleNotFoundError(
            "Spotify support requires the 'spotipy' dependency. "
            "Install project requirements to use open_spotify_session()."
        )

    def open_tidal_session(*_args, **_kwargs):  # type: ignore[no-redef]
        raise ModuleNotFoundError(
            "Tidal support requires the 'tidalapi' dependency. "
            "Install project requirements to use open_tidal_session()."
        )


__all__ = [
    "SyncEngine",
    "MatchCache",
    "open_spotify_session",
    "open_tidal_session",
]

__version__ = "2.0.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
