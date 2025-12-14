"""
Unified logging utilities for spotify2tidal.

Provides a SyncLogger class that works seamlessly in both CLI and Streamlit contexts,
with colored terminal output for CLI and session-state-based logging for web.
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional


class LogLevel(Enum):
    """Log levels with their display properties."""

    DEBUG = ("DEBUG", "🔍", "\033[90m")  # Gray
    INFO = ("INFO", "ℹ️", "\033[94m")  # Blue
    SUCCESS = ("SUCCESS", "✓", "\033[92m")  # Green
    WARNING = ("WARNING", "⚠️", "\033[93m")  # Yellow
    ERROR = ("ERROR", "❌", "\033[91m")  # Red
    PROGRESS = ("PROGRESS", "→", "\033[96m")  # Cyan

    @property
    def name_str(self) -> str:
        return self.value[0]

    @property
    def icon(self) -> str:
        return self.value[1]

    @property
    def color(self) -> str:
        return self.value[2]


RESET = "\033[0m"


@dataclass
class LogEntry:
    """A single log entry with metadata."""

    level: LogLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Optional[str] = None  # e.g., "Syncing playlist: My Favorites"

    def format_for_terminal(self, use_color: bool = True) -> str:
        """Format for CLI terminal output."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        prefix = f"[{time_str}]"

        if use_color:
            return f"{self.level.color}{prefix} {self.level.icon} {self.message}{RESET}"
        return f"{prefix} [{self.level.name_str}] {self.message}"

    def format_for_web(self) -> str:
        """Format for Streamlit display."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"`{time_str}` {self.level.icon} {self.message}"


class SyncLogger:
    """
    Unified logger for CLI and Streamlit contexts.

    Usage:
        # CLI mode (default)
        logger = SyncLogger()
        logger.info("Starting sync...")
        logger.success("Playlist synced!")

        # Web mode (Streamlit)
        logger = SyncLogger(mode="web", session_state=st.session_state)
        logger.info("Starting sync...")
        # Logs are stored in session_state["sync_logs"]
    """

    def __init__(
        self,
        mode: str = "cli",
        session_state: Optional[object] = None,
        verbose: bool = False,
        quiet: bool = False,
        use_color: bool = True,
        on_log: Optional[Callable[[LogEntry], None]] = None,
    ):
        """
        Initialize the logger.

        Args:
            mode: "cli" for terminal output, "web" for Streamlit session state
            session_state: Streamlit session_state object (required for web mode)
            verbose: If True, show DEBUG level messages
            quiet: If True, only show ERROR messages
            use_color: If True, use ANSI colors in CLI mode
            on_log: Optional callback called for each log entry
        """
        self.mode = mode
        self.session_state = session_state
        self.verbose = verbose
        self.quiet = quiet
        self.use_color = use_color and sys.stdout.isatty()
        self.on_log = on_log
        self._entries: list[LogEntry] = []

        # Initialize session state storage for web mode
        if mode == "web" and session_state is not None:
            if "sync_logs" not in session_state:
                session_state["sync_logs"] = []

    def _log(self, level: LogLevel, message: str, context: Optional[str] = None):
        """Internal logging method."""
        # Filter based on quiet/verbose settings
        if self.quiet and level not in (LogLevel.ERROR,):
            return
        if level == LogLevel.DEBUG and not self.verbose:
            return

        entry = LogEntry(level=level, message=message, context=context)
        self._entries.append(entry)

        if self.mode == "cli":
            self._output_to_terminal(entry)
        elif self.mode == "web" and self.session_state is not None:
            self._output_to_session(entry)

        if self.on_log:
            self.on_log(entry)

    def _output_to_terminal(self, entry: LogEntry):
        """Output to CLI terminal."""
        print(entry.format_for_terminal(self.use_color))

    def _output_to_session(self, entry: LogEntry):
        """Store in Streamlit session state."""
        if self.session_state is not None:
            self.session_state["sync_logs"].append(entry)

    # Public logging methods
    def debug(self, message: str, context: Optional[str] = None):
        """Log a debug message (only shown in verbose mode)."""
        self._log(LogLevel.DEBUG, message, context)

    def info(self, message: str, context: Optional[str] = None):
        """Log an informational message."""
        self._log(LogLevel.INFO, message, context)

    def success(self, message: str, context: Optional[str] = None):
        """Log a success message."""
        self._log(LogLevel.SUCCESS, message, context)

    def warning(self, message: str, context: Optional[str] = None):
        """Log a warning message."""
        self._log(LogLevel.WARNING, message, context)

    def error(self, message: str, context: Optional[str] = None):
        """Log an error message."""
        self._log(LogLevel.ERROR, message, context)

    def progress(self, message: str, context: Optional[str] = None):
        """Log a progress update."""
        self._log(LogLevel.PROGRESS, message, context)

    # Utility methods
    def get_entries(self) -> list[LogEntry]:
        """Get all log entries."""
        return self._entries.copy()

    def get_web_entries(self) -> list[LogEntry]:
        """Get log entries from session state (for web mode)."""
        if self.session_state is not None and "sync_logs" in self.session_state:
            return list(self.session_state["sync_logs"])
        return []

    def clear(self):
        """Clear all log entries."""
        self._entries.clear()
        if self.session_state is not None and "sync_logs" in self.session_state:
            self.session_state["sync_logs"].clear()

    def format_summary(self) -> str:
        """Generate a summary of logged events for display."""
        errors = sum(1 for e in self._entries if e.level == LogLevel.ERROR)
        warnings = sum(1 for e in self._entries if e.level == LogLevel.WARNING)
        successes = sum(1 for e in self._entries if e.level == LogLevel.SUCCESS)

        parts = []
        if successes:
            parts.append(f"✓ {successes} completed")
        if warnings:
            parts.append(f"⚠️ {warnings} warnings")
        if errors:
            parts.append(f"❌ {errors} errors")

        return " | ".join(parts) if parts else "No activity"


# Error message helpers for user-friendly output
class UserErrors:
    """Pre-defined user-friendly error messages with guidance."""

    @staticmethod
    def spotify_auth_failed(original_error: str) -> str:
        return (
            f"❌ Spotify authentication failed: {original_error}\n\n"
            "💡 Try these steps:\n"
            "   1. Check SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET\n"
            "   2. Verify redirect URI matches your Spotify app settings\n"
            "   3. Delete .cache file and try again to force re-auth"
        )

    @staticmethod
    def tidal_auth_failed(original_error: str) -> str:
        return (
            f"❌ Tidal authentication failed: {original_error}\n\n"
            "💡 Try these steps:\n"
            "   1. Delete library/.tidal_session.json and try again\n"
            "   2. Make sure you complete the login in the browser within 5 minutes\n"
            "   3. Check your Tidal subscription is active"
        )

    @staticmethod
    def config_not_found(path: str) -> str:
        return (
            f"❌ Configuration file not found: {path}\n\n"
            "💡 Create a config.yml file with your Spotify credentials.\n"
            "   See config.example.yml for the required format."
        )

    @staticmethod
    def network_error(original_error: str) -> str:
        return (
            f"❌ Network error: {original_error}\n\n"
            "💡 Check your internet connection and try again.\n"
            "   If the problem persists, the Spotify/Tidal API may be temporarily down."
        )

    @staticmethod
    def rate_limited() -> str:
        return (
            "⚠️ Rate limited by the API.\n\n"
            "💡 Try these options:\n"
            "   1. Wait a few minutes and try again\n"
            "   2. Reduce the rate_limit setting in config.yml\n"
            "   3. Reduce the max_concurrent setting"
        )

    @staticmethod
    def sync_error(operation: str, original_error: str) -> str:
        return (
            f"❌ Sync error during {operation}: {original_error}\n\n"
            "💡 Your progress has been cached. Run the command again to resume.\n"
            "   Use --verbose for more details."
        )
