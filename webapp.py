"""
Streamlit Web App for spotify2tidal.

A browser-based interface for syncing Spotify library to Tidal.
Deploy to Streamlit Cloud for easy access from any device.

This is the main entry point. Run with: streamlit run webapp.py
"""

import asyncio

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
    page_title="Spotify to Tidal Sync",
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
        '<h1 class="main-title">Spotify to Tidal Sync</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="main-subtitle">'
        "Transfer your Spotify library to Tidal with one click"
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

    # File upload for restoring previous export
    render_file_upload()

    # Sync options
    st.subheader("What would you like to sync?")

    col1, col2 = st.columns(2)

    with col1:
        sync_all = st.checkbox("Everything (recommended)", value=True, key="sync_all")

    with col2:
        if not sync_all:
            playlists = st.checkbox("Playlists", value=True, key="sync_playlists")
            favorites = st.checkbox("Liked Songs", value=True, key="sync_favorites")
            albums = st.checkbox("Saved Albums", value=True, key="sync_albums")
            artists = st.checkbox("Followed Artists", value=True, key="sync_artists")
            podcasts = st.checkbox(
                "Podcasts (export only)", value=False, key="sync_podcasts"
            )
        else:
            playlists = favorites = albums = artists = True
            podcasts = False

    st.divider()

    # Sync button
    st.markdown('<div class="sync-btn">', unsafe_allow_html=True)
    button_text = (
        "🔄 Sync in Progress..." if st.session_state.sync_running else "🚀 Start Sync"
    )
    if st.button(button_text, disabled=st.session_state.sync_running):
        # Store sync options and trigger rerun so UI updates before sync starts
        st.session_state.sync_running = True
        st.session_state.sync_options = {
            "all": sync_all,
            "playlists": playlists,
            "favorites": favorites,
            "albums": albums,
            "artists": artists,
            "podcasts": podcasts,
        }
        add_log("info", "Starting sync operation...")
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
            st.session_state.sync_running = False
            st.rerun()
        except Exception as e:
            st.error(f"Sync failed: {e}")
            st.session_state.sync_running = False

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
