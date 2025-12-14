"""
Session state management for the web application.
Centralizes all session state initialization and logging.
"""

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
        "tidal_session": None,
        "tidal_login_url": None,
        "tidal_device_code": None,
        "tidal_future": None,
        "sync_running": False,
        "sync_results": None,
        "sync_logs": [],
        "last_error": None,
        "export_files": {},
        # Performance settings
        "max_concurrent": max_concurrent,
        "rate_limit": rate_limit,
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


def is_ready() -> bool:
    """Check if both services are connected and ready to sync."""
    return st.session_state.spotify_connected and st.session_state.tidal_connected
