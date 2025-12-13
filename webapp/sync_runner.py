"""
Sync runner for the web application.
Handles the async sync operation with progress updates.
"""

import streamlit as st

from spotify2tidal.cache import MatchCache
from spotify2tidal.logging_utils import SyncLogger
from spotify2tidal.sync import SyncEngine

from .state import add_log


async def run_sync(
    sync_options: dict, status_placeholder, progress_placeholder
) -> dict:
    """
    Run the sync operation with progress updates.

    Args:
        sync_options: Dict with keys 'all', 'playlists', 'favorites', etc.
        status_placeholder: Streamlit placeholder for status messages
        progress_placeholder: Streamlit placeholder for progress bar

    Returns:
        Dict with sync results per category
    """
    # Create logger that writes to session state
    logger = SyncLogger(mode="web", session_state=st.session_state)

    # Use in-memory cache for web session (persists across sync runs in same session)
    if "memory_cache" not in st.session_state:
        st.session_state.memory_cache = MatchCache()  # No file = in-memory only

    cache = st.session_state.memory_cache

    engine = SyncEngine(
        st.session_state.spotify_client,
        st.session_state.tidal_session,
        max_concurrent=st.session_state.get("max_concurrent", 10),
        rate_limit=st.session_state.get("rate_limit", 10),
        library_dir=None,  # In-memory mode
        logger=logger,
        cache=cache,
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

    def update_progress(step_name: str, done: bool = False):
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

        # Export library data (returns dict with 'files' and 'stats')
        update_progress("Exporting library data...")
        if results:
            export_result = engine.export_library()
            # export_library returns {"files": {filename: content}, "stats": {...}}
            # We want just the files dict for the zip
            export_files = {}
            if export_result.get("files"):
                for key, content in export_result["files"].items():
                    # Use the key as filename (it might be a Path in file mode,
                    # or just a string key in memory mode)
                    filename = f"{key}.csv" if not str(key).endswith(".csv") else key
                    export_files[str(filename)] = content

            # Also export cache data for future restore
            import json

            export_files["cache.json"] = json.dumps(cache.to_dict(), indent=2)
            add_log("info", f"Cache saved: {cache.get_stats()}")

            st.session_state.export_files = export_files

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
