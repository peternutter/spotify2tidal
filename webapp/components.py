"""
Reusable UI components for the web application.
"""

import io
import zipfile
from datetime import datetime

import streamlit as st

from .auth import (
    check_tidal_login,
    connect_spotify,
    start_tidal_login,
)
from .state import clear_logs


def render_activity_log():
    """Render the activity log panel."""
    if st.session_state.sync_logs:
        with st.expander("Activity Log", expanded=False):
            log_html = '<div class="activity-log">'
            for entry in reversed(st.session_state.sync_logs[-50:]):
                time_str = entry.timestamp.strftime("%H:%M:%S")
                level_class = f"log-{entry.level.name_str.lower()}"
                log_html += f"""
                    <div class="log-entry">
                        <span class="log-time">{time_str}</span>
                        <span class="{level_class}">
                            {entry.level.icon} {entry.message}
                        </span>
                    </div>
                """
            log_html += "</div>"
            st.markdown(log_html, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Clear Log", key="clear_log"):
                    clear_logs()
                    st.rerun()
            with col2:
                log_text = "\n".join(
                    f"[{e.timestamp.strftime('%H:%M:%S')}] "
                    f"{e.level.name_str}: {e.message}"
                    for e in st.session_state.sync_logs
                )
                st.download_button(
                    "Download Log",
                    data=log_text,
                    file_name="sync_log.txt",
                    mime="text/plain",
                    key="download_log",
                )


def render_troubleshooting():
    """Render troubleshooting panel if there's an error."""
    if st.session_state.last_error:
        with st.expander("Troubleshooting", expanded=True):
            st.markdown(
                f'<div class="error-card">{st.session_state.last_error}</div>',
                unsafe_allow_html=True,
            )
            if st.button("✕ Dismiss", key="dismiss_error"):
                st.session_state.last_error = None
                st.rerun()


def render_spotify_connection():
    """Render Spotify connection UI in sidebar."""
    st.subheader("Spotify")
    if st.session_state.spotify_connected:
        username = st.session_state.get("spotify_user", "Unknown")
        st.markdown(
            f"""<div class="connection-card connected">
                <span class="status-dot status-connected"></span>
                <span>Connected as <strong>{username}</strong></span>
            </div>""",
            unsafe_allow_html=True,
        )
    elif st.session_state.get("spotify_auth_url"):
        st.info("Click below to log in to Spotify:")
        st.link_button(
            "🎵 Log in to Spotify",
            st.session_state.spotify_auth_url,
            use_container_width=True,
        )
        st.caption("You'll be redirected back here after login.")
    else:
        if st.button(
            "Connect Spotify", key="spotify_connect", use_container_width=True
        ):
            connect_spotify()
            st.rerun()


def render_tidal_connection():
    """Render Tidal connection UI in sidebar."""
    st.subheader("Tidal")
    if st.session_state.tidal_connected:
        st.markdown(
            """<div class="connection-card connected">
                <span class="status-dot status-connected"></span>
                <span>Connected to Tidal</span>
            </div>""",
            unsafe_allow_html=True,
        )
    elif st.session_state.tidal_login_url:
        st.info("Complete login in the popup:")
        st.code(st.session_state.tidal_device_code, language=None)
        st.link_button("🌊 Open Tidal Login", st.session_state.tidal_login_url)

        if st.button("✓ I've logged in", use_container_width=True):
            if check_tidal_login():
                st.rerun()
            else:
                st.warning(
                    "Login not detected yet. "
                    "Please complete the login and try again."
                )
    else:
        if st.button("Connect Tidal", key="tidal_connect", use_container_width=True):
            start_tidal_login()
            st.rerun()


def render_connection_status():
    """Render connection status summary."""
    st.subheader("Status")
    ready = st.session_state.spotify_connected and st.session_state.tidal_connected
    if ready:
        st.markdown(
            '<div class="success-card">✅ Ready to sync</div>',
            unsafe_allow_html=True,
        )
    else:
        missing = []
        if not st.session_state.spotify_connected:
            missing.append("Spotify")
        if not st.session_state.tidal_connected:
            missing.append("Tidal")
        st.markdown(
            f'<div class="warning-card">⚠️ Connect: {", ".join(missing)}</div>',
            unsafe_allow_html=True,
        )


def render_performance_settings():
    """Render performance settings sliders."""
    st.subheader("Performance")
    st.session_state.max_concurrent = st.slider(
        "Concurrent requests",
        min_value=1,
        max_value=50,
        value=st.session_state.get("max_concurrent", 10),
        help="Parallel API requests. Higher = faster but may hit rate limits.",
    )
    st.session_state.rate_limit = st.slider(
        "Requests per second",
        min_value=1,
        max_value=50,
        value=st.session_state.get("rate_limit", 10),
        help="Max requests per second. Higher = faster but may hit rate limits.",
    )
    st.caption("⚠️ High values may cause API errors")


def render_sync_results(results: dict):
    """Render sync results with metrics and download button."""
    st.divider()
    st.markdown(
        '<div class="success-card"><h3>Sync Complete</h3></div>',
        unsafe_allow_html=True,
    )

    for category, data in results.items():
        if isinstance(data, dict) and "added" in data:
            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"{category.title()} Added", data["added"])
            with col2:
                st.metric("Not Found", data.get("not_found", 0))
        elif isinstance(data, dict) and "exported" in data:
            st.metric(f"{category.title()} Exported", data["exported"])
        elif isinstance(data, dict):
            total_added = sum(
                d.get("added", 0) for d in data.values() if isinstance(d, dict)
            )
            total_nf = sum(
                d.get("not_found", 0) for d in data.values() if isinstance(d, dict)
            )
            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"{category.title()} Added", total_added)
            with col2:
                st.metric("Not Found", total_nf)

    # Download button for exported files
    if st.session_state.get("export_files"):
        st.divider()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, content in st.session_state.export_files.items():
                zf.writestr(filename, content)

        zip_buffer.seek(0)

        st.download_button(
            "Download Synced Data",
            data=zip_buffer.getvalue(),
            file_name=f"spotify2tidal_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            key="download_results",
            help="Download CSVs of synced and not-found items.",
        )

    if st.button("Sync Again"):
        st.session_state.sync_results = None
        st.session_state.export_files = {}
        clear_logs()
        st.rerun()
