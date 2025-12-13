"""
Session state management for the web application.
Centralizes all session state initialization and logging.
"""

from datetime import datetime

import streamlit as st

from spotify2tidal.logging_utils import LogEntry, LogLevel


def init_session_state():
    """Initialize all session state variables with defaults."""
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


def is_ready() -> bool:
    """Check if both services are connected and ready to sync."""
    return st.session_state.spotify_connected and st.session_state.tidal_connected
