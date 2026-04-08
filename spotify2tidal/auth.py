"""
Authentication helpers for Spotify, Tidal, and Apple Music.
"""

import logging
import os
import webbrowser
from pathlib import Path
from typing import Optional

import spotipy
import tidalapi
from spotipy.oauth2 import SpotifyOAuth

from .apple_music_client import AppleMusicClient

logger = logging.getLogger(__name__)

SPOTIFY_SCOPES = (
    "user-library-read "
    "user-library-modify "  # For adding tracks/albums to library
    "playlist-read-private "
    "user-follow-read "
    "user-follow-modify "  # For following artists
    "playlist-modify-private "
    "playlist-modify-public "
    "user-read-playback-position"  # Required for podcasts/shows
)


def open_spotify_session(config: dict, cache_path: Optional[str] = None) -> spotipy.Spotify:
    """
    Open a Spotify session using OAuth.

    Config can contain:
        - client_id: Spotify app client ID
        - client_secret: Spotify app client secret
        - redirect_uri: OAuth redirect URI (default: http://127.0.0.1:8888/callback)
        - username: Spotify username (optional)
        - show_dialog: Whether to force Spotify consent/account selection (default: False)
        - open_browser: Whether to open browser for auth (default: True)

    Args:
        config: Configuration dictionary
        cache_path: Path to store OAuth token cache (default: .spotify_cache in cwd)
    """
    # Allow environment variables to override config
    client_id = config.get("client_id") or os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = config.get("client_secret") or os.environ.get("SPOTIFY_CLIENT_SECRET")
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
        show_dialog=config.get("show_dialog", False),
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


def open_apple_music_session(config: dict) -> AppleMusicClient:
    """
    Open an Apple Music session using browser-extracted tokens.

    Config can contain:
        - bearer_token: Authorization Bearer token from browser DevTools
        - media_user_token: Media-User-Token header from browser DevTools
        - cookies: Cookie header from browser DevTools
        - storefront: 2-letter country code (default: "us")

    Tokens can also be set via environment variables:
        APPLE_MUSIC_BEARER_TOKEN, APPLE_MUSIC_USER_TOKEN,
        APPLE_MUSIC_COOKIES, APPLE_MUSIC_STOREFRONT
    """
    bearer_token = config.get("bearer_token") or os.environ.get("APPLE_MUSIC_BEARER_TOKEN", "")
    media_user_token = config.get("media_user_token") or os.environ.get(
        "APPLE_MUSIC_USER_TOKEN", ""
    )
    cookies = config.get("cookies") or os.environ.get("APPLE_MUSIC_COOKIES", "")
    storefront = config.get("storefront") or os.environ.get("APPLE_MUSIC_STOREFRONT", "us")

    if not bearer_token or not media_user_token:
        raise ValueError(
            "Apple Music bearer_token and media_user_token are required.\n\n"
            "To get them:\n"
            "  1. Open https://music.apple.com in your browser and sign in\n"
            "  2. Open DevTools (F12) → Network tab\n"
            "  3. Navigate to https://buy.music.apple.com/account/web/info\n"
            "  4. Find the request and copy these headers:\n"
            "     - Authorization (the Bearer token)\n"
            "     - Media-User-Token\n"
            "     - Cookie\n"
            "  5. Set them in config.yml under apple_music: or via env vars\n"
        )

    client = AppleMusicClient(
        bearer_token=bearer_token,
        media_user_token=media_user_token,
        cookies=cookies,
        storefront=storefront,
    )

    if not client.validate_session():
        raise ValueError(
            "Apple Music authentication failed. "
            "Your tokens may have expired (they last ~6 months). "
            "Re-extract them from browser DevTools."
        )

    logger.info("Apple Music session validated successfully")
    return client
