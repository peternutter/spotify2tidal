"""
Generic sync operations for syncing items between platforms.

This module provides a unified, configurable sync pattern that eliminates
code duplication across sync_favorites, sync_albums, sync_artists, and
their reverse counterparts.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    from .sync import SyncEngine

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """Configuration for a generic sync operation."""

    # Display name for logging
    item_type: str  # "track", "album", "artist"

    # Fetching functions
    fetch_source: Callable  # async () -> List[items]
    fetch_existing_ids: Callable  # async () -> Set[id]

    # Search and matching
    search_item: Callable  # async (item) -> target_id or None
    get_source_id: Callable  # (item) -> source_id
    get_cache_match: Callable  # (source_id) -> cached_id or None

    # Adding to target
    add_item: Callable  # (target_id) -> None

    # Optional: library export callbacks
    add_to_library: Optional[Callable] = None  # (items) -> None
    add_not_found: Optional[Callable] = None  # (item) -> None

    # Progress description
    progress_desc: str = "Syncing items"

    # Whether to reverse order (for chronological sync)
    reverse_order: bool = True


async def sync_items(config: SyncConfig, engine: "SyncEngine") -> Tuple[int, int]:
    """
    Generic sync operation that handles tracks, albums, or artists.

    This replaces the duplicated sync_favorites, sync_albums, sync_artists,
    and their reverse counterparts with a single configurable implementation.

    Returns: (items_added, items_not_found)
    """
    engine.rate_limiter.start()
    try:
        # Phase 1: Fetch source items
        engine._report_progress(event="phase", phase="fetching")
        source_items = await config.fetch_source()
        logger.info(f"Found {len(source_items)} {config.item_type}s from source")

        if not source_items:
            return 0, 0

        # Optionally reverse for chronological order
        if config.reverse_order:
            source_items = list(reversed(source_items))

        # Apply debug limit
        source_items = engine._apply_limit(source_items)

        # Fetch existing IDs from target
        existing_ids = await config.fetch_existing_ids()
        logger.info(f"Found {len(existing_ids)} existing {config.item_type}s on target")

        # Add to library export if available
        if config.add_to_library:
            config.add_to_library(source_items)

        # Phase 2: Search and add with progress
        added = 0
        not_found = 0
        skipped = 0

        for item in engine._progress_iter(
            source_items, config.progress_desc, phase="searching"
        ):
            source_id = config.get_source_id(item)
            from_cache = config.get_cache_match(source_id) is not None

            target_id = await config.search_item(item)

            if target_id:
                if target_id in existing_ids:
                    skipped += 1
                    engine._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                    continue  # Already exists

                try:
                    config.add_item(target_id)
                    added += 1
                    engine._report_progress(
                        event="item", matched=True, from_cache=from_cache
                    )
                except Exception as e:
                    logger.warning(f"Failed to add {config.item_type}: {e}")
                    engine._report_progress(event="item", matched=False, failed=True)
            else:
                not_found += 1
                engine._report_progress(event="item", matched=False)
                if config.add_not_found:
                    config.add_not_found(item)

        logger.info(
            f"{config.item_type.title()}s: {added} added, "
            f"{skipped} existed, {not_found} not found"
        )
        return added, not_found

    finally:
        engine.rate_limiter.stop()


async def sync_items_batched(
    config: SyncConfig,
    engine: "SyncEngine",
    batch_add: Callable[[List[Any]], None],
    batch_size: int = 50,
) -> Tuple[int, int]:
    """
    Generic sync operation for APIs that support batch adds (like Spotify).

    Similar to sync_items but collects items first, then adds in batches.

    Returns: (items_added, items_not_found)
    """
    engine.rate_limiter.start()
    try:
        # Phase 1: Fetch source items
        engine._report_progress(event="phase", phase="fetching")
        source_items = await config.fetch_source()
        logger.info(f"Found {len(source_items)} {config.item_type}s from source")

        if not source_items:
            return 0, 0

        # Apply debug limit (no reverse for batch operations)
        source_items = engine._apply_limit(source_items)

        # Fetch existing IDs from target
        existing_ids = await config.fetch_existing_ids()
        logger.info(f"Found {len(existing_ids)} existing {config.item_type}s on target")

        # Add to library export if available
        if config.add_to_library:
            config.add_to_library(source_items)

        # Phase 2: Search and collect items to add
        items_to_add = []
        not_found_count = 0

        for item in engine._progress_iter(
            source_items, config.progress_desc, phase="searching"
        ):
            source_id = config.get_source_id(item)
            from_cache = config.get_cache_match(source_id) is not None

            target_id = await config.search_item(item)

            if target_id:
                if target_id not in existing_ids:
                    items_to_add.append(target_id)
                engine._report_progress(
                    event="item", matched=True, from_cache=from_cache
                )
            else:
                not_found_count += 1
                engine._report_progress(event="item", matched=False)
                if config.add_not_found:
                    config.add_not_found(item)

        # Phase 3: Add in batches
        added = 0
        if items_to_add:
            batches = [
                items_to_add[i : i + batch_size]
                for i in range(0, len(items_to_add), batch_size)
            ]
            for batch in engine._progress_iter(
                batches, f"Adding {config.item_type}s", phase="adding"
            ):
                try:
                    batch_add(batch)
                    added += len(batch)
                except Exception as e:
                    logger.warning(f"Failed to add batch: {e}")

        logger.info(f"Added {added} {config.item_type}s, {not_found_count} not found")
        return added, not_found_count

    finally:
        engine.rate_limiter.stop()
