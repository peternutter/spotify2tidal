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
    render_performance_settings,
    render_spotify_connection,
    render_sync_results,
    render_tidal_connection,
    render_troubleshooting,
)
from webapp.state import add_log
from webapp.sync_runner import run_sync

# Page configuration
st.set_page_config(
    page_title="Spotify → Tidal Sync",
    page_icon="🎵",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Apply custom styles
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with connections and settings."""
    with st.sidebar:
        st.header("🔗 Connections")

        render_spotify_connection()
        st.divider()

        render_tidal_connection()
        st.divider()

        render_connection_status()
        st.divider()

        render_performance_settings()
        st.divider()

        st.caption("v1.2.0 • Secure & Private")
        st.caption("No data is stored on our servers.")


def render_main():
    """Render the main content area."""
    st.title("🎵 Spotify → Tidal Sync")

    st.markdown(
        """
    <p style="text-align: center; color: #8b949e; margin-bottom: 2rem;">
        Transfer your Spotify library to Tidal with one click
    </p>
    """,
        unsafe_allow_html=True,
    )

    render_troubleshooting()
    render_activity_log()

    if not is_ready():
        st.markdown(
            """
            <div class="status-card" style="text-align: center; padding: 2rem;">
                <p style="font-size: 1.2rem; margin-bottom: 1rem;">👈 Get Started</p>
                <p style="color: #8b949e;">
                    Connect to Spotify and Tidal in the sidebar to sync.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Sync options
    st.subheader("What would you like to sync?")

    col1, col2 = st.columns(2)

    with col1:
        sync_all = st.checkbox(
            "🎯 Everything (recommended)", value=True, key="sync_all"
        )

    with col2:
        if not sync_all:
            playlists = st.checkbox("📝 Playlists", value=True, key="sync_playlists")
            favorites = st.checkbox("❤️ Liked Songs", value=True, key="sync_favorites")
            albums = st.checkbox("💿 Saved Albums", value=True, key="sync_albums")
            artists = st.checkbox("🎤 Followed Artists", value=True, key="sync_artists")
            podcasts = st.checkbox(
                "🎙️ Podcasts (export only)", value=False, key="sync_podcasts"
            )
        else:
            playlists = favorites = albums = artists = True
            podcasts = False

    st.divider()

    # Sync button
    st.markdown('<div class="sync-btn">', unsafe_allow_html=True)
    if st.button("🚀 Start Sync", disabled=st.session_state.sync_running):
        st.session_state.sync_running = True
        add_log("info", "Starting sync operation...")

        sync_options = {
            "all": sync_all,
            "playlists": playlists,
            "favorites": favorites,
            "albums": albums,
            "artists": artists,
            "podcasts": podcasts,
        }

        status_placeholder = st.empty()
        progress_placeholder = st.empty()

        try:
            results = asyncio.run(
                run_sync(sync_options, status_placeholder, progress_placeholder)
            )
            st.session_state.sync_results = results
            st.session_state.sync_running = False
            st.rerun()
        except Exception as e:
            st.error(f"Sync failed: {e}")
            st.session_state.sync_running = False
    st.markdown("</div>", unsafe_allow_html=True)

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
