"""
Streamlit Web App for spotify2tidal.

A browser-based interface for syncing Spotify library to Tidal.
Deploy to Streamlit Cloud for easy access from any device.
"""

import asyncio
import io
import zipfile
from pathlib import Path

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Spotify → Tidal Sync",
    page_icon="🎵",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .stApp {
        background: linear-gradient(135deg, #1DB954 0%, #191414 50%, #00FFFF 100%);
        background-attachment: fixed;
    }
    .main .block-container {
        background: rgba(25, 20, 20, 0.95);
        border-radius: 20px;
        padding: 2rem;
        margin-top: 1rem;
    }
    h1 {
        background: linear-gradient(90deg, #1DB954, #00FFFF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
    }
    .stButton > button {
        width: 100%;
        border-radius: 25px;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .spotify-btn > button {
        background: #1DB954 !important;
        color: white !important;
    }
    .tidal-btn > button {
        background: #00FFFF !important;
        color: black !important;
    }
    .sync-btn > button {
        background: linear-gradient(90deg, #1DB954, #00FFFF) !important;
        color: white !important;
        font-size: 1.2rem !important;
        padding: 1rem !important;
    }
    .success-box {
        background: rgba(29, 185, 84, 0.2);
        border: 1px solid #1DB954;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .info-box {
        background: rgba(0, 255, 255, 0.1);
        border: 1px solid #00FFFF;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
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
        # Performance settings
        "max_concurrent": 10,
        "rate_limit": 10,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_spotify_credentials():
    """Get Spotify credentials from secrets or environment."""
    try:
        client_id = st.secrets.get("SPOTIFY_CLIENT_ID")
        client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET")
        redirect_uri = st.secrets.get("SPOTIFY_REDIRECT_URI")

        if not client_id or not client_secret:
            st.error(
                "❌ Missing Spotify credentials. "
                "Please configure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
                "in Streamlit secrets."
            )
            return None

        if not redirect_uri:
            st.error(
                "❌ Missing SPOTIFY_REDIRECT_URI in Streamlit secrets. "
                "Set it to your deployed URL (e.g., https://spotify2tidal.streamlit.app/)"
            )
            return None

        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    except Exception as e:
        st.error(f"❌ Failed to load Spotify credentials: {e}")
        return None


def get_spotify_auth_manager():
    """Get a SpotifyOAuth manager for web flow."""
    from spotipy.oauth2 import SpotifyOAuth

    creds = get_spotify_credentials()
    if not creds:
        return None

    # Use cache_handler=None to avoid file-based caching issues on Streamlit Cloud
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
        open_browser=False,  # Don't open browser on server
        cache_handler=None,  # Don't use file cache
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
                # Exchange code for access token
                token_info = auth_manager.get_access_token(code)

                # Handle both dict (current) and string (future) responses
                if isinstance(token_info, dict):
                    access_token = token_info["access_token"]
                else:
                    access_token = token_info

                # Create Spotify client with token
                spotify = spotipy.Spotify(auth=access_token)

                # Test connection and get user info
                user = spotify.current_user()
                st.session_state.spotify_client = spotify
                st.session_state.spotify_token_info = token_info
                st.session_state.spotify_connected = True
                st.session_state.spotify_user = user["display_name"] or user["id"]

                # Clear the code from URL to avoid re-processing
                st.query_params.clear()
                return True
            except Exception as e:
                st.error(f"Failed to complete Spotify login: {e}")
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
    # For web deployment, we just show the auth URL
    # The actual connection happens in handle_spotify_callback() after redirect
    auth_url = get_spotify_auth_url()
    if auth_url:
        st.session_state.spotify_auth_url = auth_url
        return True
    return False


def start_tidal_login():
    """Start Tidal OAuth device flow."""
    import tidalapi

    session = tidalapi.Session()
    login, future = session.login_oauth()

    url = login.verification_uri_complete
    if not url.startswith("https://"):
        url = "https://" + url

    st.session_state.tidal_session = session
    st.session_state.tidal_login_url = url
    st.session_state.tidal_device_code = login.user_code
    st.session_state.tidal_future = future


def check_tidal_login():
    """Check if Tidal login completed."""
    if st.session_state.tidal_future and st.session_state.tidal_session:
        future = st.session_state.tidal_future
        if future.done():
            try:
                future.result()
                if st.session_state.tidal_session.check_login():
                    st.session_state.tidal_connected = True
                    # Save session for future use
                    session_file = Path.home() / ".tidal_session.json"
                    st.session_state.tidal_session.save_session_to_file(session_file)
                    return True
            except Exception:
                pass
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
                return True
        except Exception:
            pass
    return False


async def run_sync(sync_options, status_placeholder, progress_placeholder):
    """Run the sync operation with progress updates."""
    from spotify2tidal.sync import SyncEngine

    engine = SyncEngine(
        st.session_state.spotify_client,
        st.session_state.tidal_session,
        max_concurrent=st.session_state.get("max_concurrent", 10),
        rate_limit=st.session_state.get("rate_limit", 10),
        library_dir="./library",
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
        progress = steps_done / max(total_steps, 1)
        progress_placeholder.progress(progress)
        status_placeholder.info(f"🔄 {step_name}")

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

    return results


def render_sidebar():
    """Render the sidebar with connection status."""
    with st.sidebar:
        st.header("🔗 Connections")

        # Spotify connection
        st.subheader("Spotify")
        if st.session_state.spotify_connected:
            st.success(
                f"✓ Connected as {st.session_state.get('spotify_user', 'Unknown')}"
            )
        elif st.session_state.get("spotify_auth_url"):
            # Show link to Spotify login
            st.info("Click the button below to log in to Spotify:")
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
            st.success("✓ Connected to Tidal")
        elif st.session_state.tidal_login_url:
            # Show login instructions
            st.info("Complete login in the popup:")
            st.code(st.session_state.tidal_device_code, language=None)
            st.link_button("🔗 Open Tidal Login", st.session_state.tidal_login_url)

            # Check if login completed
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
                    # Try existing session first
                    if not try_load_existing_tidal_session():
                        start_tidal_login()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Status summary
        st.subheader("Status")
        ready = st.session_state.spotify_connected and st.session_state.tidal_connected
        if ready:
            st.success("✅ Ready to sync!")
        else:
            missing = []
            if not st.session_state.spotify_connected:
                missing.append("Spotify")
            if not st.session_state.tidal_connected:
                missing.append("Tidal")
            st.warning(f"Connect: {', '.join(missing)}")

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
            help="Max requests per second. Higher = faster, but may hit rate limits.",
        )
        st.caption("⚠️ High values may cause API errors")

        st.divider()

        # Simple backup/restore
        st.subheader("💾 Backup")

        # Restore from backup (always available)
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
                    st.success("✅ Restored!")
                else:
                    cache_path = Path.home() / ".spotify2tidal_cache.db"
                    with open(cache_path, "wb") as f:
                        f.write(uploaded.getvalue())
                    st.success("✅ Cache restored!")
            except Exception as e:
                st.error(f"Restore failed: {e}")

        # Download backup (if cache exists)
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
    <p style="text-align: center; color: #888; margin-bottom: 2rem;">
        Transfer your Spotify library to Tidal with one click
    </p>
    """,
        unsafe_allow_html=True,
    )

    # Check if ready
    ready = st.session_state.spotify_connected and st.session_state.tidal_connected

    if not ready:
        st.info("👈 Connect to Spotify and Tidal in the sidebar to get started")
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
            podcasts = False  # Podcasts not synced to Tidal, so off by default

    st.divider()

    # Sync button
    st.markdown('<div class="sync-btn">', unsafe_allow_html=True)
    if st.button("🚀 Start Sync", disabled=st.session_state.sync_running):
        st.session_state.sync_running = True

        sync_options = {
            "all": sync_all,
            "playlists": playlists,
            "favorites": favorites,
            "albums": albums,
            "artists": artists,
            "podcasts": podcasts,
        }

        # Create placeholders for progress updates
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
        st.subheader("✅ Sync Complete!")

        results = st.session_state.sync_results

        for category, data in results.items():
            if isinstance(data, dict) and "added" in data:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(f"{category.title()} Added", data["added"])
                with col2:
                    st.metric("Not Found", data.get("not_found", 0))
            elif isinstance(data, dict):
                # Playlist results: dict of playlist_name -> {added, not_found}
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
