"""
Session state management for the web application.
Centralizes all session state initialization and logging.
"""

import asyncio
import threading
import time
from datetime import datetime

import streamlit as st

from spotify2tidal.logging_utils import LogEntry, LogLevel


def _get_secret_or_env(key: str):
    """Get a value from Streamlit secrets or environment variables."""
    # st.secrets behaves like a mapping; .get() is safe even if key missing
    val = st.secrets.get(key)
    if val is not None:
        return val
    import os

    return os.environ.get(key)


def _parse_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class GlobalThrottle:
    """
    Cross-session throttle for Streamlit Cloud.

    Uses threading primitives so it is safe even if Streamlit creates multiple event
    loops over time (e.g. via asyncio.run). Provides a RateLimiter-like interface:
    - async acquire()
    - release()
    - start()/stop() no-ops
    """

    def __init__(self, max_concurrent: int, rate_per_second: float):
        self._semaphore = threading.BoundedSemaphore(max(1, int(max_concurrent)))
        self._rate = float(rate_per_second) if rate_per_second else 0.0
        self._lock = threading.Lock()
        self._next_allowed: float = 0.0  # time.monotonic() seconds

    def start(self):
        """Backward-compatible no-op."""
        return

    def stop(self):
        """Backward-compatible no-op."""
        return

    async def acquire(self):
        """Acquire a global concurrency slot and pace requests across all sessions."""
        # Concurrency gate (thread-safe, loop-agnostic)
        await asyncio.to_thread(self._semaphore.acquire)

        # Optional pacing gate
        if self._rate <= 0:
            return

        interval = 1.0 / self._rate
        with self._lock:
            now = time.monotonic()
            wait_for = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + interval

        if wait_for > 0:
            await asyncio.sleep(wait_for)

    def release(self):
        """Release a previously acquired global concurrency slot."""
        try:
            self._semaphore.release()
        except ValueError:
            # Shouldn't happen, but don't crash if release is mismatched.
            pass


@st.cache_resource(show_spinner=False)
def get_global_throttle(max_concurrent: int, rate_limit: float) -> GlobalThrottle:
    """
    Get a single global throttle shared across all sessions in this Streamlit process.

    NOTE: This is per Streamlit worker process (good enough for Streamlit Cloud).
    """
    return GlobalThrottle(max_concurrent=max_concurrent, rate_per_second=rate_limit)


def init_session_state():
    """Initialize all session state variables with defaults."""
    # Conservative defaults for public multi-user hosting; override via secrets/env.
    max_concurrent = _parse_int(_get_secret_or_env("MAX_CONCURRENT"), 5)
    rate_limit = _parse_float(_get_secret_or_env("RATE_LIMIT"), 5.0)

    # Guardrails: avoid pathological settings in public deployments.
    max_concurrent = max(1, min(max_concurrent, 25))
    rate_limit = max(0.5, min(rate_limit, 25.0))

    defaults = {
        "spotify_connected": False,
        "tidal_connected": False,
        "spotify_client": None,
        # Token store used by Spotipy cache_handler. Must be a plain dict so it can
        # be safely accessed by worker threads (no ScriptRunContext required).
        "spotify_token_store": {},
        "tidal_session": None,
        "tidal_login_url": None,
        "tidal_device_code": None,
        "tidal_future": None,
        "sync_running": False,
        # Last chosen sync direction: "to_tidal" or "to_spotify"
        "sync_direction": "to_tidal",
        "sync_results": None,
        "sync_logs": [],
        "last_error": None,
        "last_traceback": None,
        "export_files": {},
        "sync_started_at": None,
        "sync_last_progress_at": None,
        # Resumable sync: track completed steps for resume after interruption
        "sync_progress": {},  # e.g. {"favorites": True, "playlists": True}
        "sync_options_saved": None,  # Original options for resume
        # Performance settings
        "max_concurrent": max_concurrent,
        "rate_limit": rate_limit,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Warm the global throttle so it exists before any sync begins.
    # This is a no-op on subsequent runs.
    get_global_throttle(max_concurrent, rate_limit)

    # Migration: older sessions stored token directly under spotify_token_info.
    # Copy it into the token store if present so Spotipy can read it from threads.
    if (
        "spotify_token_info" in st.session_state
        and isinstance(st.session_state.get("spotify_token_info"), dict)
        and isinstance(st.session_state.get("spotify_token_store"), dict)
        and not st.session_state["spotify_token_store"].get("token_info")
    ):
        st.session_state["spotify_token_store"]["token_info"] = st.session_state[
            "spotify_token_info"
        ]


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


def is_ready() -> bool:
    """Check if both services are connected and ready to sync."""
    return st.session_state.spotify_connected and st.session_state.tidal_connected
