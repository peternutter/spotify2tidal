"""
Sync runner for the web application.
Handles the async sync operation with progress updates.
"""

import time
import traceback

import streamlit as st

from spotify2tidal.cache import MatchCache
from spotify2tidal.logging_utils import SyncLogger
from spotify2tidal.sync import SyncEngine

from .state import add_log, get_global_throttle


async def run_sync(
    sync_options: dict, status_placeholder, progress_bar, details_placeholder=None
) -> dict:
    """
    Run the sync operation with progress updates.

    Args:
        sync_options: Dict with keys 'all', 'playlists', 'favorites', etc.
        status_placeholder: Streamlit placeholder for status messages
        progress_bar: Streamlit progress bar widget
        details_placeholder: Streamlit placeholder for detailed progress stats

    Returns:
        Dict with sync results per category
    """
    if details_placeholder is None:
        details_placeholder = st.empty()

    direction = sync_options.get("direction", "to_tidal")
    item_limit = sync_options.get("item_limit")
    if item_limit:
        add_log("warning", f"⚠️  Test run enabled: limiting to {int(item_limit)} items")
    # Create logger that writes to session state
    logger = SyncLogger(mode="web", session_state=st.session_state)

    # Use in-memory cache for web session (persists across sync runs in same session)
    if "memory_cache" not in st.session_state:
        st.session_state.memory_cache = MatchCache()  # No file = in-memory only

    cache = st.session_state.memory_cache

    # Progress tracking state
    progress_state = {
        "current": 0,
        "total": 0,
        "matched": 0,
        "not_found": 0,
        "failed": 0,
        "cache_hits": 0,
        "phase": "searching",
    }

    def progress_callback(
        event: str,
        current: int = 0,
        total: int = 0,
        phase: str = "processing",
        from_cache: bool = False,
        matched: bool = True,
        failed: bool = False,
    ):
        """Handle progress events from the sync engine."""
        if event == "update":
            # Heartbeat for diagnosing interrupted reruns / stalls.
            st.session_state.sync_last_progress_at = time.time()
            progress_state["current"] = current
            progress_state["total"] = total
            progress_state["phase"] = phase
            _update_progress_display()
        elif event == "item":
            if failed:
                progress_state.setdefault("failed", 0)
                progress_state["failed"] += 1
            else:
                if matched:
                    progress_state["matched"] += 1
                else:
                    progress_state["not_found"] += 1
            if from_cache:
                progress_state["cache_hits"] += 1
        elif event == "total":
            progress_state["total"] = total
            _update_progress_display()
        elif event == "phase":
            progress_state["phase"] = phase
            _update_progress_display()

    def _update_progress_display():
        """Update the progress display in Streamlit."""
        current = progress_state["current"]
        total = progress_state["total"]
        phase = progress_state["phase"]

        phase_emoji = {
            "fetching": "📥",
            "searching": "🔍",
            "adding": "➕",
            "exporting": "📤",
        }.get(phase, "⏳")

        # When fetching, we often don't know the final total yet.
        # Still show *something* so users can tell the app is working.
        if total > 0:
            progress_frac = min(1.0, current / total)
            progress_bar.progress(
                progress_frac, text=f"{phase_emoji} {current:,} / {total:,}"
            )
        else:
            if current > 0:
                progress_bar.progress(0.0, text=f"{phase_emoji} {current:,} items")
            else:
                phase_label = {
                    "fetching": "Fetching",
                    "searching": "Searching",
                    "adding": "Adding",
                    "exporting": "Exporting",
                }.get(phase, "Working")
                progress_bar.progress(0.0, text=f"{phase_emoji} {phase_label}...")

    # Cross-session throttle (shared within the Streamlit worker process)
    global_throttle = get_global_throttle(
        st.session_state.get("max_concurrent", 5),
        st.session_state.get("rate_limit", 5.0),
    )

    engine = SyncEngine(
        st.session_state.spotify_client,
        st.session_state.tidal_session,
        max_concurrent=st.session_state.get("max_concurrent", 10),
        rate_limit=st.session_state.get("rate_limit", 10),
        library_dir=None,  # In-memory mode
        logger=logger,
        cache=cache,
        rate_limiter=global_throttle,
        progress_callback=progress_callback,
        item_limit=int(item_limit) if item_limit else None,
    )

    results = {}
    steps = []

    # Determine which steps to run
    if direction == "to_spotify":
        # Reverse sync (Tidal -> Spotify). We currently support
        # favorites/albums/artists/playlists.
        if sync_options.get("all") or sync_options.get("playlists"):
            steps.append(("playlists", "Syncing Tidal playlists to Spotify"))
        if sync_options.get("all") or sync_options.get("favorites"):
            steps.append(("favorites", "Syncing Tidal favorites to Spotify"))
        if sync_options.get("all") or sync_options.get("albums"):
            steps.append(("albums", "Syncing Tidal albums to Spotify"))
        if sync_options.get("all") or sync_options.get("artists"):
            steps.append(("artists", "Syncing Tidal artists to Spotify"))
    else:
        # Default direction (Spotify -> Tidal).
        if sync_options.get("all") or sync_options.get("playlists"):
            steps.append(("playlists", "Syncing playlists"))
        if sync_options.get("all") or sync_options.get("favorites"):
            steps.append(("favorites", "Syncing liked songs"))
        if sync_options.get("all") or sync_options.get("albums"):
            steps.append(("albums", "Syncing saved albums"))
        if sync_options.get("all") or sync_options.get("artists"):
            steps.append(("artists", "Syncing followed artists"))
        if sync_options.get("all") or sync_options.get("podcasts"):
            steps.append(("podcasts", "Exporting podcasts"))

    total_steps = len(steps)
    steps_done = 0

    try:
        for step_key, step_name in steps:
            # Reset per-step progress
            progress_state["current"] = 0
            progress_state["total"] = 0

            add_log("progress", f"{step_name}...")
            status_placeholder.info(f"🔄 {step_name}...")
            progress_bar.progress(0, text=f"🔄 {step_name}...")

            # Show step-level details
            step_info = f"**Step {steps_done + 1}/{total_steps}**: {step_name}"
            details_placeholder.markdown(step_info)

            if direction == "to_spotify":
                if step_key == "playlists":
                    results["playlists"] = await engine.sync_all_playlists_to_spotify()
                elif step_key == "favorites":
                    added, nf = await engine.sync_favorites_to_spotify()
                    results["favorites"] = {"added": added, "not_found": nf}
                elif step_key == "albums":
                    added, nf = await engine.sync_albums_to_spotify()
                    results["albums"] = {"added": added, "not_found": nf}
                elif step_key == "artists":
                    added, nf = await engine.sync_artists_to_spotify()
                    results["artists"] = {"added": added, "not_found": nf}
            else:
                if step_key == "playlists":
                    results["playlists"] = await engine.sync_all_playlists()
                elif step_key == "favorites":
                    added, nf = await engine.sync_favorites()
                    results["favorites"] = {"added": added, "not_found": nf}
                elif step_key == "albums":
                    added, nf = await engine.sync_albums()
                    results["albums"] = {"added": added, "not_found": nf}
                elif step_key == "artists":
                    added, nf = await engine.sync_artists()
                    results["artists"] = {"added": added, "not_found": nf}
                elif step_key == "podcasts":
                    count = await engine.export_podcasts()
                    results["podcasts"] = {"exported": count}

            steps_done += 1
            add_log("success", f"{step_name} ✓")

            # Update overall progress between steps
            overall_progress = steps_done / max(total_steps, 1)
            progress_bar.progress(overall_progress, text=f"✓ {step_name} complete")

        # Export data bundle
        status_placeholder.info("🔄 Exporting data...")
        progress_bar.progress(0.95, text="📤 Exporting...")
        add_log("progress", "Exporting data...")

        if results:
            export_files = {}

            export_result = await engine.export_backup()
            if export_result.get("files"):
                for key, content in export_result["files"].items():
                    filename = f"{key}.csv" if not str(key).endswith(".csv") else key
                    export_files[str(filename)] = content

            # Also export cache data for future restore
            import json

            export_files["cache.json"] = json.dumps(cache.to_dict(), indent=2)
            add_log("info", f"Cache saved: {cache.get_stats()}")

            st.session_state.export_files = export_files

        # Show completion
        status_placeholder.success("✅ Sync complete!")
        progress_bar.progress(1.0, text="✅ Complete!")

        # Final stats summary
        cache_stats = cache.get_stats()
        with details_placeholder.container():
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Matched", f"{progress_state['matched']:,}")
            with col2:
                st.metric("Not found", f"{progress_state['not_found']:,}")
            with col3:
                st.metric("Failed adds", f"{progress_state.get('failed', 0):,}")

            # Secondary metric below the main summary row
            st.caption(
                f"Cache (track matches): {cache_stats.get('cached_track_matches', 0):,}"
            )

        add_log("success", "Sync completed successfully!")

    except Exception as e:
        add_log("error", f"Sync failed: {e}")
        st.session_state.last_traceback = traceback.format_exc()
        st.session_state.last_error = (
            f"**Sync Error**\n\n{e}\n\n"
            "Your progress has been cached. Try running sync again to resume."
        )
        raise

    return results
