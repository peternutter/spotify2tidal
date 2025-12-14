"""
Progress tracking utilities for the web application.
Provides detailed progress information including items/second, ETA, etc.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class ProgressPhase(Enum):
    """Current phase of the sync operation."""

    FETCHING = "fetching"
    SEARCHING = "searching"
    ADDING = "adding"
    EXPORTING = "exporting"


@dataclass
class ProgressStats:
    """Detailed progress statistics."""

    # Current phase info
    category: str = ""  # playlists, favorites, albums, artists, podcasts
    phase: ProgressPhase = ProgressPhase.FETCHING

    # Item counts
    current: int = 0
    total: int = 0

    # Timing
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    # Cumulative stats across all categories
    total_processed: int = 0
    total_matched: int = 0
    total_not_found: int = 0
    cache_hits: int = 0

    def update(
        self,
        current: int,
        total: Optional[int] = None,
        phase: Optional[ProgressPhase] = None,
    ):
        """Update progress with new values."""
        self.current = current
        if total is not None:
            self.total = total
        if phase is not None:
            self.phase = phase
        self.last_update = time.time()

    def set_category(self, category: str):
        """Set the current category being processed."""
        self.category = category
        self.current = 0
        self.total = 0
        self.start_time = time.time()

    @property
    def elapsed_seconds(self) -> float:
        """Total elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def items_per_second(self) -> float:
        """Current processing rate in items per second."""
        elapsed = self.elapsed_seconds
        if elapsed <= 0 or self.current <= 0:
            return 0.0
        return self.current / elapsed

    @property
    def eta_seconds(self) -> float:
        """Estimated time remaining in seconds."""
        if self.items_per_second <= 0 or self.current >= self.total:
            return 0.0
        remaining = self.total - self.current
        return remaining / self.items_per_second

    @property
    def progress_fraction(self) -> float:
        """Progress as a fraction (0.0 to 1.0)."""
        if self.total <= 0:
            return 0.0
        return min(1.0, self.current / self.total)

    def format_eta(self) -> str:
        """Format ETA as human-readable string."""
        eta = self.eta_seconds
        if eta <= 0:
            return ""
        if eta < 60:
            return f"{int(eta)}s"
        elif eta < 3600:
            minutes = int(eta // 60)
            seconds = int(eta % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(eta // 3600)
            minutes = int((eta % 3600) // 60)
            return f"{hours}h {minutes}m"

    def format_speed(self) -> str:
        """Format processing speed."""
        speed = self.items_per_second
        if speed <= 0:
            return ""
        if speed >= 1:
            return f"{speed:.1f} it/s"
        else:
            # Less than 1 item per second, show seconds per item
            return f"{1/speed:.1f} s/it"

    def format_status(self) -> str:
        """Format a detailed status message."""
        parts = []

        # Category and phase
        phase_labels = {
            ProgressPhase.FETCHING: "📥 Fetching",
            ProgressPhase.SEARCHING: "🔍 Searching",
            ProgressPhase.ADDING: "➕ Adding",
            ProgressPhase.EXPORTING: "📤 Exporting",
        }
        phase_label = phase_labels.get(self.phase, "⏳ Processing")

        if self.category:
            parts.append(f"{phase_label} {self.category}")
        else:
            parts.append(phase_label)

        # Progress count
        if self.total > 0:
            parts.append(f"{self.current}/{self.total}")
        elif self.current > 0:
            parts.append(f"{self.current} items")

        # Speed
        speed = self.format_speed()
        if speed:
            parts.append(f"({speed})")

        # ETA
        eta = self.format_eta()
        if eta:
            parts.append(f"ETA: {eta}")

        return " • ".join(parts)

    def format_summary(self) -> str:
        """Format a cumulative summary."""
        parts = []
        if self.total_matched > 0:
            parts.append(f"✅ {self.total_matched} matched")
        if self.total_not_found > 0:
            parts.append(f"❌ {self.total_not_found} not found")
        if self.cache_hits > 0:
            parts.append(f"💾 {self.cache_hits} from cache")
        return " | ".join(parts) if parts else ""


class ProgressTracker:
    """
    Track progress across multiple sync operations.
    Provides callbacks for updating UI components.
    """

    def __init__(self, on_update: Optional[Callable[[ProgressStats], None]] = None):
        self.stats = ProgressStats()
        self.on_update = on_update
        self._category_totals: dict = {}

    def set_on_update(self, callback: Callable[[ProgressStats], None]):
        """Set the callback for progress updates."""
        self.on_update = callback

    def start_category(self, category: str, total: int = 0):
        """Start tracking a new category."""
        self.stats.set_category(category)
        self.stats.total = total
        self._notify()

    def update(
        self,
        current: int,
        total: Optional[int] = None,
        phase: Optional[ProgressPhase] = None,
    ):
        """Update current progress."""
        self.stats.update(current, total, phase)
        self._notify()

    def increment(self, matched: bool = True, from_cache: bool = False):
        """Increment progress by 1."""
        self.stats.current += 1
        self.stats.total_processed += 1
        if matched:
            self.stats.total_matched += 1
        else:
            self.stats.total_not_found += 1
        if from_cache:
            self.stats.cache_hits += 1
        self._notify()

    def set_phase(self, phase: ProgressPhase):
        """Set the current processing phase."""
        self.stats.phase = phase
        self._notify()

    def _notify(self):
        """Notify the UI of progress update."""
        if self.on_update:
            self.on_update(self.stats)

    def get_stats(self) -> ProgressStats:
        """Get current progress stats."""
        return self.stats
