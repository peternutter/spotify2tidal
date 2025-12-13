"""
Streamlit Web App for spotify2tidal.

A browser-based interface for syncing Spotify library to Tidal.
Deploy to Streamlit Cloud for easy access from any device.

Production-ready with activity logging, user-friendly errors, and polished UI.
"""

import asyncio
import io
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from spotify2tidal.logging_utils import LogEntry, LogLevel, SyncLogger

# Page configuration
st.set_page_config(
    page_title="Spotify → Tidal Sync",
    page_icon="🎵",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished, modern styling
st.markdown(
    """
<style>
    /* Main background with subtle gradient */
    .stApp {
        background: linear-gradient(160deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
        background-attachment: fixed;
    }

    /* Main container styling */
    .main .block-container {
        background: rgba(22, 27, 34, 0.95);
        border-radius: 16px;
        padding: 2rem;
        margin-top: 1rem;
        border: 1px solid rgba(48, 54, 61, 0.8);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    /* Title gradient */
    h1 {
        background: linear-gradient(135deg, #1DB954 0%, #1ed760 50%, #00d4aa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    /* Subheaders */
    h2, h3 {
        color: #e6edf3 !important;
        font-weight: 600;
    }

    /* Button styling */
    .stButton > button {
        width: 100%;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.2s ease;
        border: none;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    /* Spotify brand button */
    .spotify-btn > button {
        background: linear-gradient(135deg, #1DB954 0%, #1ed760 100%) !important;
        color: white !important;
    }

    /* Tidal brand button */
    .tidal-btn > button {
        background: linear-gradient(135deg, #00FFFF 0%, #00d4aa 100%) !important;
        color: #0d1117 !important;
    }

    /* Primary sync button */
    .sync-btn > button {
        background: linear-gradient(135deg, #1DB954 0%, #00FFFF 100%) !important;
        color: white !important;
        font-size: 1.1rem !important;
        padding: 1rem 2rem !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
    }

    /* Card-like containers */
    .status-card {
        background: rgba(48, 54, 61, 0.5);
        border: 1px solid rgba(48, 54, 61, 0.8);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    .success-card {
        background: rgba(29, 185, 84, 0.15);
        border: 1px solid rgba(29, 185, 84, 0.4);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    .warning-card {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.4);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    .error-card {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.4);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    /* Activity log styling */
    .activity-log {
        background: rgba(13, 17, 23, 0.8);
        border: 1px solid rgba(48, 54, 61, 0.6);
        border-radius: 8px;
        padding: 0.75rem;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.85rem;
        max-height: 300px;
        overflow-y: auto;
    }

    .log-entry {
        padding: 0.25rem 0;
        border-bottom: 1px solid rgba(48, 54, 61, 0.3);
    }

    .log-entry:last-child {
        border-bottom: none;
    }

    .log-time {
        color: #8b949e;
        margin-right: 0.5rem;
    }

    .log-success { color: #3fb950; }
    .log-warning { color: #d29922; }
    .log-error { color: #f85149; }
    .log-info { color: #58a6ff; }
    .log-progress { color: #a371f7; }

    /* Divider styling */
    hr {
        border-color: rgba(48, 54, 61, 0.6) !important;
        margin: 1.5rem 0 !important;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: rgba(22, 27, 34, 0.98);
        border-right: 1px solid rgba(48, 54, 61, 0.6);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    /* Metric styling */
    [data-testid="stMetric"] {
        background: rgba(48, 54, 61, 0.3);
        border-radius: 8px;
        padding: 0.75rem;
    }

    /* Connection status dots */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-connected { background: #3fb950; box-shadow: 0 0 8px #3fb950; }
    .status-disconnected { background: #8b949e; }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "spotify_connected": False,
        "tidal_connected": False,
        "spotify_client": None,
        "tidal_session": None,
        "tidal_login_url": None,
        "tidal_device_code": None,
        "tidal_future": None,
        "sync_running": False,
        "sync_results": None,
        "sync_logs": [],  # Activity log entries
        "last_error": None,  # Last error for troubleshooting
        # Performance settings
        "max_concurrent": 10,
        "rate_limit": 10,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_log(level: str, message: str):
    """Add a log entry to the session state."""
    entry = LogEntry(
        level=LogLevel[level.upper()],
        message=message,
        timestamp=datetime.now(),
    )
    st.session_state.sync_logs.append(entry)


def clear_logs():
    """Clear all log entries."""
    st.session_state.sync_logs = []


def get_spotify_credentials():
    """Get Spotify credentials from secrets or environment."""
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


def handle_spotify_callback():
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


def get_spotify_auth_url():
    """Get the Spotify authorization URL for the user to click."""
    auth_manager = get_spotify_auth_manager()
    if auth_manager:
        return auth_manager.get_authorize_url()
    return None


def connect_spotify():
    """Connect to Spotify using OAuth - web flow version."""
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


def check_tidal_login():
    """Check if Tidal login completed."""
    if st.session_state.tidal_future and st.session_state.tidal_session:
        future = st.session_state.tidal_future
        if future.done():
            try:
                future.result()
                if st.session_state.tidal_session.check_login():
                    st.session_state.tidal_connected = True
                    session_file = Path.home() / ".tidal_session.json"
                    st.session_state.tidal_session.save_session_to_file(session_file)
                    add_log("success", "Connected to Tidal")
                    return True
            except Exception as e:
                add_log("error", f"Tidal login check failed: {e}")
    return False


def try_load_existing_tidal_session():
    """Try to load an existing Tidal session."""
    import tidalapi

    session_file = Path.home() / ".tidal_session.json"
    if session_file.exists():
        try:
            session = tidalapi.Session()
            session.load_session_from_file(session_file)
            if session.check_login():
                st.session_state.tidal_session = session
                st.session_state.tidal_connected = True
                add_log("success", "Loaded existing Tidal session")
                return True
        except Exception as e:
            add_log("warning", f"Could not load Tidal session: {e}")
    return False


async def run_sync(sync_options, status_placeholder, progress_placeholder):
    """Run the sync operation with progress updates."""
    from spotify2tidal.sync import SyncEngine

    # Create logger that writes to session state
    logger = SyncLogger(mode="web", session_state=st.session_state)

    engine = SyncEngine(
        st.session_state.spotify_client,
        st.session_state.tidal_session,
        max_concurrent=st.session_state.get("max_concurrent", 10),
        rate_limit=st.session_state.get("rate_limit", 10),
        library_dir="./library",
        logger=logger,
    )

    results = {}
    steps_done = 0
    total_steps = sum(
        [
            sync_options.get("all") or sync_options.get("playlists", False),
            sync_options.get("all") or sync_options.get("favorites", False),
            sync_options.get("all") or sync_options.get("albums", False),
            sync_options.get("all") or sync_options.get("artists", False),
            sync_options.get("all") or sync_options.get("podcasts", False),
        ]
    )

    def update_progress(step_name, done=False):
        nonlocal steps_done
        if done:
            steps_done += 1
            add_log("success", step_name)
        else:
            add_log("progress", step_name)
        progress = steps_done / max(total_steps, 1)
        progress_placeholder.progress(progress)
        status_placeholder.info(f"🔄 {step_name}")

    try:
        if sync_options.get("all") or sync_options.get("playlists"):
            update_progress("Syncing playlists...")
            results["playlists"] = await engine.sync_all_playlists()
            update_progress("Playlists synced ✓", done=True)

        if sync_options.get("all") or sync_options.get("favorites"):
            update_progress("Syncing liked songs (this may take a while)...")
            added, nf = await engine.sync_favorites()
            results["favorites"] = {"added": added, "not_found": nf}
            update_progress("Liked songs synced ✓", done=True)

        if sync_options.get("all") or sync_options.get("albums"):
            update_progress("Syncing saved albums...")
            added, nf = await engine.sync_albums()
            results["albums"] = {"added": added, "not_found": nf}
            update_progress("Albums synced ✓", done=True)

        if sync_options.get("all") or sync_options.get("artists"):
            update_progress("Syncing followed artists...")
            added, nf = await engine.sync_artists()
            results["artists"] = {"added": added, "not_found": nf}
            update_progress("Artists synced ✓", done=True)

        if sync_options.get("all") or sync_options.get("podcasts"):
            update_progress("Exporting podcasts to CSV...")
            count = await engine.export_podcasts()
            results["podcasts"] = {"exported": count}
            update_progress("Podcasts exported ✓", done=True)

        # Export library data
        update_progress("Exporting library data...")
        if results:
            export_result = engine.export_library()
            st.session_state.export_files = export_result.get("files", {})

        status_placeholder.success("✅ Sync complete!")
        progress_placeholder.progress(1.0)
        add_log("success", "Sync completed successfully!")

    except Exception as e:
        add_log("error", f"Sync failed: {e}")
        st.session_state.last_error = (
            f"**Sync Error**\n\n{e}\n\n"
            "Your progress has been cached. Try running sync again to resume."
        )
        raise

    return results


def render_activity_log():
    """Render the activity log panel."""
    if st.session_state.sync_logs:
        with st.expander("📋 Activity Log", expanded=False):
            log_html = '<div class="activity-log">'
            for entry in reversed(st.session_state.sync_logs[-50:]):  # Show last 50
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
                if st.button("🗑️ Clear Log", key="clear_log"):
                    clear_logs()
                    st.rerun()
            with col2:
                # Export log as text
                log_text = "\n".join(
                    f"[{e.timestamp.strftime('%H:%M:%S')}] "
                    f"{e.level.name_str}: {e.message}"
                    for e in st.session_state.sync_logs
                )
                st.download_button(
                    "📥 Download Log",
                    data=log_text,
                    file_name="sync_log.txt",
                    mime="text/plain",
                    key="download_log",
                )


def render_troubleshooting():
    """Render troubleshooting panel if there's an error."""
    if st.session_state.last_error:
        with st.expander("🔧 Troubleshooting", expanded=True):
            st.markdown(
                f'<div class="error-card">{st.session_state.last_error}</div>',
                unsafe_allow_html=True,
            )
            if st.button("✕ Dismiss", key="dismiss_error"):
                st.session_state.last_error = None
                st.rerun()


def render_sidebar():
    """Render the sidebar with connection status."""
    with st.sidebar:
        st.header("🔗 Connections")

        # Spotify connection
        st.subheader("Spotify")
        if st.session_state.spotify_connected:
            username = st.session_state.get("spotify_user", "Unknown")
            st.markdown(
                f"""<div class="status-card">
                    <span class="status-dot status-connected"></span>
                    Connected as <strong>{username}</strong>
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
            with st.container():
                st.markdown('<div class="spotify-btn">', unsafe_allow_html=True)
                if st.button("🎵 Connect Spotify", key="spotify_connect"):
                    connect_spotify()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Tidal connection
        st.subheader("Tidal")
        if st.session_state.tidal_connected:
            st.markdown(
                """<div class="status-card">
                    <span class="status-dot status-connected"></span>
                    Connected to Tidal
                </div>""",
                unsafe_allow_html=True,
            )
        elif st.session_state.tidal_login_url:
            st.info("Complete login in the popup:")
            st.code(st.session_state.tidal_device_code, language=None)
            st.link_button("🔗 Open Tidal Login", st.session_state.tidal_login_url)

            if st.button("✓ I've logged in"):
                if check_tidal_login():
                    st.rerun()
                else:
                    st.warning(
                        "Login not detected yet. "
                        "Please complete the login and try again."
                    )
        else:
            with st.container():
                st.markdown('<div class="tidal-btn">', unsafe_allow_html=True)
                if st.button("🌊 Connect Tidal", key="tidal_connect"):
                    if not try_load_existing_tidal_session():
                        start_tidal_login()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Status summary
        st.subheader("Status")
        ready = st.session_state.spotify_connected and st.session_state.tidal_connected
        if ready:
            st.markdown(
                '<div class="success-card">✅ Ready to sync!</div>',
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

        st.divider()

        # Performance settings
        st.subheader("⚡ Performance")
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

        st.divider()

        # Backup/restore
        st.subheader("💾 Backup")

        uploaded = st.file_uploader(
            "Restore from backup",
            type=["zip", "db"],
            key="restore_backup",
            help="Upload a .zip backup or .db cache file",
        )
        if uploaded:
            try:
                if uploaded.name.endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(uploaded.getvalue()), "r") as zf:
                        if "spotify2tidal_cache.db" in zf.namelist():
                            cache_path = Path.home() / ".spotify2tidal_cache.db"
                            with open(cache_path, "wb") as f:
                                f.write(zf.read("spotify2tidal_cache.db"))
                        library_dir = Path("./library")
                        library_dir.mkdir(exist_ok=True)
                        for filename in zf.namelist():
                            if filename.endswith(".csv"):
                                with open(library_dir / filename, "wb") as f:
                                    f.write(zf.read(filename))
                    add_log("success", "Backup restored successfully")
                    st.success("✅ Restored!")
                else:
                    cache_path = Path.home() / ".spotify2tidal_cache.db"
                    with open(cache_path, "wb") as f:
                        f.write(uploaded.getvalue())
                    add_log("success", "Cache database restored")
                    st.success("✅ Cache restored!")
            except Exception as e:
                add_log("error", f"Restore failed: {e}")
                st.error(f"Restore failed: {e}")

        cache_path = Path.home() / ".spotify2tidal_cache.db"
        if cache_path.exists():
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(cache_path, "spotify2tidal_cache.db")
                library_dir = Path("./library")
                if library_dir.exists():
                    for csv_file in library_dir.glob("*.csv"):
                        zf.write(csv_file, csv_file.name)
            zip_buffer.seek(0)
            st.download_button(
                "📦 Download Backup",
                data=zip_buffer.getvalue(),
                file_name="spotify2tidal_backup.zip",
                mime="application/zip",
                key="sidebar_backup",
            )


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

    # Show troubleshooting if there's an error
    render_troubleshooting()

    # Show activity log
    render_activity_log()

    # Check if ready
    ready = st.session_state.spotify_connected and st.session_state.tidal_connected

    if not ready:
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
        st.divider()
        st.markdown(
            '<div class="success-card"><h3>✅ Sync Complete!</h3></div>',
            unsafe_allow_html=True,
        )

        results = st.session_state.sync_results

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

        st.info(
            "💡 Use the **Backup** section in the sidebar to download your sync data."
        )

        if st.button("🔄 Sync Again"):
            st.session_state.sync_results = None
            st.session_state.export_files = {}
            clear_logs()
            st.rerun()


def main():
    """Main application entry point."""
    init_session_state()

    # Handle OAuth callback from Spotify (before rendering UI)
    handle_spotify_callback()

    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
