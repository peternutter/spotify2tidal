"""
Authentication helpers for Spotify and Tidal OAuth flows.
Used by the web application for user login.
"""

import os
from typing import Any, Optional

import streamlit as st

from .state import add_log


def _get_spotipy_cache_handler_base():
    """Import Spotipy CacheHandler base class lazily.

    Spotipy asserts that cache_handler is a subclass of CacheHandler.
    Importing lazily keeps import side-effects local to Spotify flows.
    """

    try:
        from spotipy.cache_handler import CacheHandler

        return CacheHandler
    except Exception:
        return None


_SpotipyCacheHandlerBase = _get_spotipy_cache_handler_base() or object


class _StreamlitSessionCacheHandler(_SpotipyCacheHandlerBase):
    """Spotipy cache handler backed by Streamlit session_state."""

    def __init__(self, key: str = "spotify_token_info"):
        self.key = key

    def get_cached_token(self) -> Optional[dict[str, Any]]:
        token = st.session_state.get(self.key)
        return token if isinstance(token, dict) else None

    def save_token_to_cache(self, token_info: dict[str, Any]) -> None:
        st.session_state[self.key] = token_info

    def delete_cached_token(self) -> None:
        st.session_state.pop(self.key, None)


def _infer_local_streamlit_redirect_uri() -> str:
    """
    Infer a reasonable redirect URI for local Streamlit runs.

    Spotify needs this to match exactly one of the app's registered Redirect URIs.
    """
    port = st.get_option("server.port") or 8501
    address = st.get_option("server.address") or "localhost"
    # Streamlit is often served on 0.0.0.0 locally; browsers should use localhost.
    if address in ("0.0.0.0", "127.0.0.1"):
        address = "localhost"
    return f"http://{address}:{port}/"


def get_spotify_credentials() -> Optional[dict]:
    """Get Spotify credentials from Streamlit secrets (or env vars for local dev)."""
    try:
        # Prefer Streamlit secrets (Streamlit Cloud / Settings → Secrets)
        client_id = st.secrets.get("SPOTIFY_CLIENT_ID") or os.environ.get(
            "SPOTIFY_CLIENT_ID"
        )
        client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET") or os.environ.get(
            "SPOTIFY_CLIENT_SECRET"
        )
        redirect_uri = st.secrets.get("SPOTIFY_REDIRECT_URI") or os.environ.get(
            "SPOTIFY_REDIRECT_URI"
        )

        if not client_id or not client_secret:
            add_log("error", "Missing Spotify credentials in secrets")
            st.session_state.last_error = (
                "**Missing Spotify Credentials**\n\n"
                "Configure `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` "
                "in Streamlit secrets (Settings → Secrets)."
            )
            return None

        if not redirect_uri:
            # For local runs, default to the Streamlit server URL (e.g. http://localhost:8501/)
            redirect_uri = _infer_local_streamlit_redirect_uri()
            add_log(
                "warning",
                "SPOTIFY_REDIRECT_URI not set; using local Streamlit URL "
                f"({redirect_uri}).",
            )

        # Guardrail: 8888/callback is the CLI default;
        # Streamlit webapp won't be listening there.
        if "127.0.0.1:8888" in redirect_uri or "localhost:8888" in redirect_uri:
            st.session_state.last_error = (
                "**Spotify Redirect URI is set to the CLI callback**\n\n"
                f"Your redirect URI is currently:\n`{redirect_uri}`\n\n"
                "For the Streamlit webapp, set `SPOTIFY_REDIRECT_URI` to your "
                "Streamlit URL (usually `http://localhost:8501/`) and add the "
                "same value in the Spotify Developer Dashboard → your app → "
                "Edit Settings → Redirect URIs.\n\n"
                "Then restart the Streamlit app and try again."
            )
            add_log(
                "error", "Spotify redirect URI points to :8888 (CLI), not Streamlit."
            )
            return None

        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    except Exception as e:
        add_log("error", f"Failed to load credentials: {e}")
        st.session_state.last_error = f"**Credentials Error**: {e}"
        return None


def get_spotify_auth_manager():
    """Get a SpotifyOAuth manager for web flow."""
    from spotipy.oauth2 import SpotifyOAuth

    creds = get_spotify_credentials()
    if not creds:
        return None

    return SpotifyOAuth(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        redirect_uri=creds["redirect_uri"],
        scope=(
            "user-library-read "
            "playlist-read-private "
            "user-follow-read "
            "playlist-modify-private "
            "playlist-modify-public "
            "user-read-playback-position"
        ),
        open_browser=False,
        cache_handler=_StreamlitSessionCacheHandler(),
    )


def get_spotify_auth_url() -> Optional[str]:
    """Get the Spotify authorization URL for the user to click."""
    auth_manager = get_spotify_auth_manager()
    if auth_manager:
        return auth_manager.get_authorize_url()
    return None


def handle_spotify_callback() -> bool:
    """Check for and handle Spotify OAuth callback in URL parameters."""
    import spotipy

    query_params = st.query_params
    code = query_params.get("code")

    if code and not st.session_state.spotify_connected:
        auth_manager = get_spotify_auth_manager()
        if auth_manager:
            try:
                add_log("info", "Processing Spotify login...")
                # This will also persist token_info into session_state
                # via cache_handler.
                token_info = auth_manager.get_access_token(code, check_cache=False)

                spotify = spotipy.Spotify(auth_manager=auth_manager)
                user = spotify.current_user()

                st.session_state.spotify_client = spotify
                st.session_state.spotify_token_info = token_info
                st.session_state.spotify_auth_manager = auth_manager
                st.session_state.spotify_connected = True
                st.session_state.spotify_user = user["display_name"] or user["id"]

                add_log(
                    "success",
                    f"Connected to Spotify as {st.session_state.spotify_user}",
                )
                st.query_params.clear()
                return True
            except Exception as e:
                add_log("error", f"Spotify login failed: {e}")
                st.session_state.last_error = (
                    f"**Spotify Login Failed**\n\n{e}\n\n"
                    "Try clearing your browser cookies and logging in again."
                )
                st.query_params.clear()
    return False


def connect_spotify() -> bool:
    """Initiate Spotify OAuth flow."""
    add_log("info", "Initiating Spotify login...")
    auth_url = get_spotify_auth_url()
    if auth_url:
        st.session_state.spotify_auth_url = auth_url
        return True
    return False


def start_tidal_login():
    """Start Tidal OAuth device flow."""
    import tidalapi

    add_log("info", "Starting Tidal device login...")
    session = tidalapi.Session()
    login, future = session.login_oauth()

    url = login.verification_uri_complete
    if not url.startswith("https://"):
        url = "https://" + url

    st.session_state.tidal_session = session
    st.session_state.tidal_login_url = url
    st.session_state.tidal_device_code = login.user_code
    st.session_state.tidal_future = future
    add_log("info", "Tidal login URL generated.")


def check_tidal_login() -> bool:
    """Check if Tidal login completed."""
    if st.session_state.tidal_future and st.session_state.tidal_session:
        future = st.session_state.tidal_future
        if future.done():
            try:
                future.result()
                if st.session_state.tidal_session.check_login():
                    st.session_state.tidal_connected = True
                    add_log("success", "Connected to Tidal")
                    return True
            except Exception as e:
                add_log("error", f"Tidal login check failed: {e}")
    return False
