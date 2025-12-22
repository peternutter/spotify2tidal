"""
Reusable UI components for the web application.
"""

import html
import io
import json
import platform
import zipfile
from datetime import datetime

import streamlit as st

from .auth import (
    check_tidal_login,
    connect_spotify,
    start_tidal_login,
)
from .state import add_log


def _safe_debug_state() -> dict:
    """Return a sanitized view of session_state suitable for sharing."""

    # Never include tokens/sessions/clients in exported debug info.
    allowlist = {
        "spotify_connected",
        "tidal_connected",
        "sync_running",
        "sync_started_at",
        "sync_last_progress_at",
        "max_concurrent",
        "rate_limit",
    }

    out: dict = {}
    for key in allowlist:
        if key in st.session_state:
            out[key] = st.session_state.get(key)

    # Add a tiny summary of results (not the content).
    results = st.session_state.get("sync_results")
    if isinstance(results, dict):
        out["sync_results_keys"] = sorted(results.keys())

    # Add basic runtime metadata.
    out["python"] = platform.python_version()
    out["platform"] = platform.platform()
    out["streamlit"] = getattr(st, "__version__", None)

    return out


def _build_debug_bundle_zip() -> bytes:
    """Build a small zip with logs + error + traceback + sanitized state."""

    # Log text (same format as Download Log)
    log_text = "\n".join(
        f"[{e.timestamp.strftime('%H:%M:%S')}] {e.level.name_str}: {e.message}"
        for e in st.session_state.get("sync_logs", [])
    )

    last_error = st.session_state.get("last_error") or ""
    last_traceback = st.session_state.get("last_traceback") or ""
    debug_state = json.dumps(_safe_debug_state(), indent=2, default=str)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sync_log.txt", log_text)
        zf.writestr("last_error.md", str(last_error))
        zf.writestr("traceback.txt", str(last_traceback))
        zf.writestr("debug_state.json", debug_state)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def render_file_upload():
    """
    Render file upload UI for restoring a previous export.
    Users can upload a .zip file from a previous sync to pre-load cache data.
    """
    with st.expander("📦 Upload Previous Export (Optional)", expanded=False):
        st.caption(
            "Upload a .zip file from a previous sync to restore your match cache. "
            "This speeds up syncing by reusing previous track matches."
        )

        uploaded_file = st.file_uploader(
            "Choose a .zip file",
            type=["zip"],
            key="upload_zip",
            help="Upload a spotify2tidal_export_*.zip file from a previous sync",
        )

        if uploaded_file is not None:
            try:
                # Safety limits (avoid zip bombs / runaway memory)
                max_zip_bytes = 20 * 1024 * 1024  # 20 MB
                max_entries = 50
                max_uncompressed_bytes = 50 * 1024 * 1024  # 50 MB total extracted

                uploaded_size = getattr(uploaded_file, "size", None)
                if uploaded_size is not None and uploaded_size > max_zip_bytes:
                    st.error(
                        f"❌ File too large ({uploaded_size / 1024 / 1024:.1f} MB). "
                        f"Max allowed is {max_zip_bytes / 1024 / 1024:.0f} MB."
                    )
                    return

                raw = uploaded_file.getvalue()
                if len(raw) > max_zip_bytes:
                    st.error(
                        f"❌ File too large ({len(raw) / 1024 / 1024:.1f} MB). "
                        f"Max allowed is {max_zip_bytes / 1024 / 1024:.0f} MB."
                    )
                    return

                zip_buffer = io.BytesIO(raw)
                with zipfile.ZipFile(zip_buffer, "r") as zf:
                    infos = zf.infolist()
                    if len(infos) > max_entries:
                        st.error(
                            f"❌ Archive contains too many files ({len(infos)}). "
                            f"Max allowed is {max_entries}."
                        )
                        return

                    total_uncompressed = sum(i.file_size for i in infos)
                    if total_uncompressed > max_uncompressed_bytes:
                        st.error(
                            f"❌ Archive is too large when extracted "
                            f"({total_uncompressed / 1024 / 1024:.1f} MB). "
                            f"Max allowed is "
                            f"{max_uncompressed_bytes / 1024 / 1024:.0f} MB."
                        )
                        return

                    file_list = [i.filename for i in infos]
                    st.success(f"✅ Loaded {len(file_list)} files from archive")

                    # Show contents
                    with st.expander("📄 Archive Contents", expanded=False):
                        for filename in file_list:
                            st.text(f"  • {filename}")

                    # Parse and load data into session state
                    loaded_data = {}
                    for filename in file_list:
                        # Only allow flat files, no directories / traversal.
                        if (
                            "/" in filename
                            or "\\" in filename
                            or filename.startswith(("/", "\\"))
                            or ".." in filename
                        ):
                            raise ValueError("Archive contains unsafe file paths.")

                        lower = filename.lower()
                        if not (
                            lower.endswith(".csv")
                            or lower.endswith(".json")
                            or lower.endswith(".opml")
                        ):
                            raise ValueError(
                                f"Archive contains unsupported file type: {filename}"
                            )

                        if filename.endswith(".csv") or filename.endswith(".opml"):
                            content = zf.read(filename).decode("utf-8")
                            loaded_data[filename] = content
                        elif filename.endswith(".json"):
                            content = zf.read(filename).decode("utf-8")
                            loaded_data[filename] = json.loads(content)

                    # Store in session state for sync_runner to use
                    st.session_state.uploaded_export = loaded_data

                    # Load cache data if present (cache.json)
                    if "cache.json" in loaded_data:
                        cache_data = loaded_data["cache.json"]
                        _restore_cache_from_json(cache_data)
                        add_log("info", "Restored match cache from uploaded file")
                        st.info(
                            f"🔄 Restored cache: "
                            f"{len(cache_data.get('tracks', {}))} tracks, "
                            f"{len(cache_data.get('albums', {}))} albums, "
                            f"{len(cache_data.get('artists', {}))} artists"
                        )

            except zipfile.BadZipFile:
                st.error("❌ Invalid zip file. Please upload a valid .zip archive.")
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")


def _restore_cache_from_json(cache_data: dict):
    """Restore the in-memory cache from JSON data."""
    from spotify2tidal.cache import MatchCache

    # Initialize cache if not present
    if "memory_cache" not in st.session_state:
        st.session_state.memory_cache = MatchCache()  # No file = in-memory only

    cache = st.session_state.memory_cache

    # Restore track matches
    for spotify_id, tidal_id in cache_data.get("tracks", {}).items():
        cache.cache_track_match(spotify_id, int(tidal_id))

    # Restore album matches
    for spotify_id, tidal_id in cache_data.get("albums", {}).items():
        cache.cache_album_match(spotify_id, int(tidal_id))

    # Restore artist matches
    for spotify_id, tidal_id in cache_data.get("artists", {}).items():
        cache.cache_artist_match(spotify_id, int(tidal_id))


def render_activity_log():
    """Render the activity log panel in the sidebar."""
    if not st.session_state.sync_logs:
        return

    with st.expander("📋 Activity Log", expanded=False):
        # Build compact HTML log entries
        log_entries = []
        for entry in reversed(st.session_state.sync_logs[-30:]):
            time_str = entry.timestamp.strftime("%H:%M:%S")
            level_class = f"log-{entry.level.name_str.lower()}"
            safe_message = html.escape(str(entry.message))
            log_entries.append(
                f'<div class="log-entry">'
                f'<span class="log-time">{time_str}</span>'
                f'<span class="{level_class}">{safe_message}</span>'
                f"</div>"
            )

        log_html = f'<div class="activity-log">{"".join(log_entries)}</div>'
        st.markdown(log_html, unsafe_allow_html=True)

        # Download button only (removed Clear button for simplicity)
        log_text = "\n".join(
            f"[{e.timestamp.strftime('%H:%M:%S')}] {e.level.name_str}: {e.message}"
            for e in st.session_state.sync_logs
        )
        st.download_button(
            "📥 Download Log",
            data=log_text,
            file_name="sync_log.txt",
            mime="text/plain",
            key="download_log",
            use_container_width=True,
        )

        # Debug bundle is useful even if the UI got into a weird state.
        st.download_button(
            "🧰 Download Debug Bundle",
            data=_build_debug_bundle_zip(),
            file_name=f"spotify2tidal_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            key="download_debug_bundle",
            use_container_width=True,
            help="Includes logs + error + traceback + sanitized app state (no tokens).",
        )


def render_troubleshooting():
    """Render troubleshooting panel if there's an error."""
    if st.session_state.last_error:
        with st.expander("Troubleshooting", expanded=True):
            # Render as Markdown
            # (HTML is escaped by default unless unsafe_allow_html=True)
            st.error("An error occurred.")
            st.markdown(st.session_state.last_error)

            tb = st.session_state.get("last_traceback")
            if tb:
                with st.expander("Show traceback", expanded=False):
                    st.code(tb, language="text")

            st.download_button(
                "🧰 Download Debug Bundle",
                data=_build_debug_bundle_zip(),
                file_name=f"spotify2tidal_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                key="download_debug_bundle_troubleshooting",
                use_container_width=True,
            )
            if st.button("✕ Dismiss", key="dismiss_error"):
                st.session_state.last_error = None
                st.session_state.last_traceback = None
                st.rerun()


def render_spotify_connection():
    """Render Spotify connection UI in sidebar."""
    st.subheader("Spotify")
    if st.session_state.spotify_connected:
        username = html.escape(str(st.session_state.get("spotify_user", "Unknown")))
        st.markdown(
            f"""<div class="connection-card connected">
                <span class="status-dot status-connected"></span>
                <span>Connected as <strong>{username}</strong></span>
            </div>""",
            unsafe_allow_html=True,
        )
    elif st.session_state.get("spotify_auth_url"):
        st.info("Click below to log in to Spotify:")
        # Use Streamlit's native link_button for reliable cross-browser behavior
        # Opens in new tab, which is standard OAuth UX that works everywhere
        st.link_button(
            "🎵 Log in to Spotify",
            st.session_state.spotify_auth_url,
            use_container_width=True,
        )
        st.caption("Complete login in the new tab, then return here.")
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
                    "Login not detected yet. Please complete the login and try again."
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
        direction = st.session_state.get("sync_direction", "to_tidal")
        direction_label = (
            "Spotify → Tidal" if direction != "to_spotify" else "Tidal → Spotify"
        )
        st.markdown(
            f'<div class="success-card">✅ Ready to sync<br/>'
            f'<span style="color: var(--text-2); font-size: 0.95rem;">'
            f"Flow: {direction_label}</span></div>",
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
