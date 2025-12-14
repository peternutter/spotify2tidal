"""
Authentication helpers for Spotify and Tidal.
"""

import logging
import os
import webbrowser
from pathlib import Path
from typing import Optional

import spotipy
import tidalapi
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

SPOTIFY_SCOPES = (
    "user-library-read "
    "playlist-read-private "
    "user-follow-read "
    "playlist-modify-private "
    "playlist-modify-public "
    "user-read-playback-position"  # Required for podcasts/shows
)


def open_spotify_session(
    config: dict, cache_path: Optional[str] = None
) -> spotipy.Spotify:
    """
    Open a Spotify session using OAuth.

    Config can contain:
        - client_id: Spotify app client ID
        - client_secret: Spotify app client secret
        - redirect_uri: OAuth redirect URI (default: http://127.0.0.1:8888/callback)
        - username: Spotify username (optional)
        - open_browser: Whether to open browser for auth (default: True)

    Args:
        config: Configuration dictionary
        cache_path: Path to store OAuth token cache (default: .spotify_cache in cwd)
    """
    # Allow environment variables to override config
    client_id = config.get("client_id") or os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = config.get("client_secret") or os.environ.get(
        "SPOTIFY_CLIENT_SECRET"
    )
    redirect_uri = config.get("redirect_uri", "http://127.0.0.1:8888/callback")

    if not client_id or not client_secret:
        raise ValueError(
            "Spotify client_id and client_secret are required. "
            "Set them in config.yml or via SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET env vars. "
            "Get them from https://developer.spotify.com/dashboard"
        )

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SPOTIFY_SCOPES,
        username=config.get("username"),
        open_browser=config.get("open_browser", True),
        cache_path=cache_path,
    )

    return spotipy.Spotify(auth_manager=auth_manager)


def open_tidal_session(
    config: Optional[dict] = None, session_file: Optional[str] = None
) -> tidalapi.Session:
    """
    Open a Tidal session using OAuth.

    Attempts to load existing session from file, otherwise initiates OAuth flow.

    Args:
        config: Config dict, can contain 'session_file' key
        session_file: Direct path to session file (overrides config)
                      Default: library/.tidal_session.json
    """
    config = config or {}

    # Priority: direct parameter > config > default
    if session_file:
        session_path = Path(session_file)
    elif config.get("session_file"):
        session_path = Path(config["session_file"]).expanduser()
    else:
        session_path = Path.home() / ".tidal_session.json"

    session = tidalapi.Session()

    # Try to load existing session
    if session_path.exists():
        try:
            session.load_session_from_file(session_path)
            if session.check_login():
                logger.info("Loaded existing Tidal session")
                return session
        except Exception as e:
            logger.warning(f"Could not load Tidal session: {e}")

    # Start OAuth flow
    logger.info("Starting Tidal OAuth login...")

    # Use the newer OAuth flow that opens a browser
    login, future = session.login_oauth()

    url = login.verification_uri_complete
    if not url.startswith("https://"):
        url = "https://" + url

    print(f"\nPlease open this URL to log in to Tidal:\n{url}\n")
    print(f"Or use device code: {login.user_code}")

    try:
        webbrowser.open(url)
    except Exception:
        pass  # Browser open failed, user can use the URL manually

    # Wait for auth to complete
    future.result()

    if session.check_login():
        # Save session for future use
        session.save_session_to_file(session_path)
        logger.info("Tidal login successful, session saved")
        return session
    else:
        raise ValueError("Could not connect to Tidal")
