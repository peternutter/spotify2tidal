"""
Streamlit Web App for spotify2tidal.

A browser-based interface for syncing Spotify library to Tidal.
Deploy to Streamlit Cloud for easy access from any device.

This is the main entry point. Run with: streamlit run webapp.py
"""

import asyncio
import time

import streamlit as st

from webapp import CUSTOM_CSS, handle_spotify_callback, init_session_state, is_ready
from webapp.components import (
    render_activity_log,
    render_connection_status,
    render_file_upload,
    render_spotify_connection,
    render_sync_results,
    render_tidal_connection,
    render_troubleshooting,
)
from webapp.state import add_log
from webapp.sync_runner import run_sync

# Page configuration
st.set_page_config(
    page_title="Spotify ↔ Tidal Sync",
    page_icon="S",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Apply custom styles
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with connections and settings."""
    with st.sidebar:
        st.header("Connections")

        render_spotify_connection()
        st.divider()

        render_tidal_connection()
        st.divider()

        render_connection_status()
        st.divider()

        render_activity_log()

        st.caption("v1.2.0")
        st.caption(
            "Your data is processed by the server running this app for the duration of "
            "your session. The app does not intentionally persist your library or "
            "tokens to disk. For maximum privacy, deploy privately."
        )


def render_main():
    """Render the main content area."""
    st.markdown(
        '<h1 class="main-title">Spotify ↔ Tidal Sync</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="main-subtitle">'
        "Use a unified library as ground truth to sync either direction"
        "</p>",
        unsafe_allow_html=True,
    )

    render_troubleshooting()

    if not is_ready():
        st.markdown(
            """
            <div class="get-started-card">
                <h3>🎵 Get Started</h3>
                <p>Connect to Spotify and Tidal in the sidebar to begin
                syncing your library.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # If the app reruns while a sync was in-flight, we can end up with
    # sync_running=True but sync_options already cleared (we clear it to prevent
    # accidental duplicate syncs). In that case, the UI can look "stuck".
    if st.session_state.sync_running and not st.session_state.get("sync_options"):
        st.warning(
            "A previous sync appears to have been interrupted. "
            "Reset to re-enable the Start Sync button."
        )
        if st.button("Reset sync", key="reset_sync", use_container_width=True):
            st.session_state.sync_running = False
            st.session_state.sync_options = None
            add_log("warning", "Sync state reset after interruption")
            st.rerun()

    # File upload for restoring previous export
    render_file_upload()

    # Sync options
    st.subheader("What would you like to sync?")

    # Users choose direction by which Start button they press.
    # Show options for the *last* chosen direction to avoid confusion.
    direction = st.session_state.get("sync_direction", "to_tidal")

    if direction == "to_spotify":
        st.caption("Current flow: Tidal → Spotify (favorites, albums, artists).")
    else:
        st.caption(
            "Current flow: Spotify → Tidal (playlists, liked songs, albums, artists)."
        )

    col1, col2 = st.columns(2)
    with col1:
        sync_all = st.checkbox(
            "Everything (recommended)",
            value=True,
            key="sync_all",
        )

    with col2:
        if direction == "to_spotify":
            if not sync_all:
                favorites = st.checkbox(
                    "Favorites / Liked Songs", value=True, key="sync_favorites"
                )
                albums = st.checkbox("Albums", value=True, key="sync_albums")
                artists = st.checkbox("Artists", value=True, key="sync_artists")
            else:
                favorites = albums = artists = True
            playlists = False
            podcasts = False
        else:
            if not sync_all:
                playlists = st.checkbox("Playlists", value=True, key="sync_playlists")
                favorites = st.checkbox("Liked Songs", value=True, key="sync_favorites")
                albums = st.checkbox("Saved Albums", value=True, key="sync_albums")
                artists = st.checkbox(
                    "Followed Artists", value=True, key="sync_artists"
                )
                podcasts = st.checkbox(
                    "Podcasts (export only)", value=False, key="sync_podcasts"
                )
            else:
                playlists = favorites = albums = artists = True
                podcasts = False

    st.divider()

    # Debug / test-run options
    col1, col2 = st.columns([1, 1])
    with col1:
        test_run = st.checkbox(
            "Test run (limit items)",
            value=False,
            key="test_run",
            help="For debugging: limits how many items are processed per category.",
        )
    with col2:
        item_limit = None
        if test_run:
            item_limit = st.number_input(
                "Item limit",
                min_value=1,
                value=50,
                step=1,
                key="item_limit",
                help="Matches the CLI --limit behavior.",
            )

    # Start buttons (choose direction)
    st.markdown('<div class="sync-btn">', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    if st.session_state.sync_running:
        col_a.button(
            "🔄 Sync in Progress...",
            disabled=True,
            use_container_width=True,
            key="sync_in_progress_left",
        )
        col_b.button(
            "🔄 Sync in Progress...",
            disabled=True,
            use_container_width=True,
            key="sync_in_progress_right",
        )
    else:
        if col_a.button(
            "🚀 Start Spotify → Tidal",
            disabled=st.session_state.sync_running,
            use_container_width=True,
            key="start_to_tidal",
        ):
            st.session_state.sync_direction = "to_tidal"
            st.session_state.sync_running = True
            st.session_state.sync_started_at = time.time()
            st.session_state.last_error = None
            st.session_state.last_traceback = None
            st.session_state.sync_options = {
                "direction": "to_tidal",
                "all": sync_all,
                "playlists": playlists,
                "favorites": favorites,
                "albums": albums,
                "artists": artists,
                "podcasts": podcasts,
                "item_limit": int(item_limit) if item_limit else None,
            }
            add_log("info", "Starting Spotify → Tidal sync...")
            st.rerun()

        if col_b.button(
            "🚀 Start Tidal → Spotify",
            disabled=st.session_state.sync_running,
            use_container_width=True,
            key="start_to_spotify",
        ):
            st.session_state.sync_direction = "to_spotify"
            st.session_state.sync_running = True
            st.session_state.sync_started_at = time.time()
            st.session_state.last_error = None
            st.session_state.last_traceback = None
            st.session_state.sync_options = {
                "direction": "to_spotify",
                "all": sync_all,
                "playlists": False,
                "favorites": favorites,
                "albums": albums,
                "artists": artists,
                "podcasts": False,
                "item_limit": int(item_limit) if item_limit else None,
            }
            add_log("info", "Starting Tidal → Spotify sync...")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Run sync if triggered (runs after the rerun, so button shows "in progress")
    if st.session_state.sync_running and st.session_state.get("sync_options"):
        sync_options = st.session_state.sync_options
        st.session_state.sync_options = None  # Clear to prevent re-running

        # Show initial progress UI
        status_text = st.empty()
        status_text.info("🔄 Starting sync...")
        progress_bar = st.progress(0, text="Preparing...")
        details_area = st.empty()

        try:
            results = asyncio.run(
                run_sync(
                    sync_options,
                    status_text,
                    progress_bar,
                    details_area,
                )
            )
            st.session_state.sync_results = results
        except Exception as e:
            # `run_sync` already stores a user-friendly message in session_state.
            # We still show a short error here as immediate feedback.
            st.error(f"Sync failed: {e}")
        finally:
            # Always reset + rerun so the UI updates (re-enables the button and
            # shows troubleshooting panel / results in a clean state).
            st.session_state.sync_running = False
            st.rerun()

    # Show results
    if st.session_state.sync_results:
        render_sync_results(st.session_state.sync_results)


def main():
    """Main application entry point."""
    init_session_state()
    handle_spotify_callback()
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
