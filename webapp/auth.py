"""
Authentication helpers for Spotify and Tidal OAuth flows.
Used by the web application for user login.
"""

from typing import Optional

import streamlit as st

from .state import add_log


def get_spotify_credentials() -> Optional[dict]:
    """Get Spotify credentials from Streamlit secrets."""
    try:
        client_id = st.secrets.get("SPOTIFY_CLIENT_ID")
        client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET")
        redirect_uri = st.secrets.get("SPOTIFY_REDIRECT_URI")

        if not client_id or not client_secret:
            add_log("error", "Missing Spotify credentials in secrets")
            st.session_state.last_error = (
                "**Missing Spotify Credentials**\n\n"
                "Configure `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` "
                "in Streamlit secrets (Settings → Secrets)."
            )
            return None

        if not redirect_uri:
            add_log("error", "Missing SPOTIFY_REDIRECT_URI in secrets")
            st.session_state.last_error = (
                "**Missing Redirect URI**\n\n"
                "Set `SPOTIFY_REDIRECT_URI` in secrets to your app URL "
                "(e.g., `https://spotify2tidal.streamlit.app/`)"
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
        cache_handler=None,
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
                token_info = auth_manager.get_access_token(code)

                if isinstance(token_info, dict):
                    access_token = token_info["access_token"]
                else:
                    access_token = token_info

                spotify = spotipy.Spotify(auth=access_token)
                user = spotify.current_user()

                st.session_state.spotify_client = spotify
                st.session_state.spotify_token_info = token_info
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
    add_log("info", f"Tidal login URL generated. Device code: {login.user_code}")


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
