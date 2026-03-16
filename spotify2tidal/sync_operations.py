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
    from .sync_engine import SyncEngine

from .retry_utils import retry_async_call

logger = logging.getLogger(__name__)


def _log_not_found(engine: "SyncEngine", item_type: str, not_found_items: List[str]):
    """Log not-found items through the engine's SyncLogger so they appear in CLI output."""
    if not not_found_items:
        return
    sync_logger = getattr(engine, "_logger", None)
    if sync_logger:
        sync_logger.warning(f"  {len(not_found_items)} {item_type}(s) not found:")
        for name in not_found_items:
            sync_logger.warning(f"    ✗ {name}")
    else:
        logger.warning(f"Not found {item_type}s:")
        for name in not_found_items:
            logger.warning(f"  ✗ {name}")


def _get_item_name(item, item_type: str) -> str:
    """Extract a human-readable name from various item formats."""
    if isinstance(item, dict):
        # Spotify-style dict
        inner = item.get("track", item) if item_type == "track" else item.get("album", item)
        name = inner.get("name", "?")
        artists = inner.get("artists", [])
        artist = artists[0]["name"] if artists else "?"
        return f"{artist} - {name}"
    # Tidal-style object
    name = getattr(item, "name", "?")
    artists = getattr(item, "artists", None) or []
    artist = artists[0].name if artists else "?"
    return f"{artist} - {name}"


@dataclass
class SyncConfig:
    """Configuration for a generic sync operation."""

    # Display name for logging
    item_type: str  # "track", "album", "artist"

    # Fetching functions
    fetch_source: Callable  # async () -> List[items]

    # Search and matching
    search_item: Callable  # async (item) -> target_id or None
    get_source_id: Callable  # (item) -> source_id
    get_cache_match: Callable  # (source_id) -> cached_id or None

    # Adding to target
    add_item: Callable  # (target_id) -> None

    # Optional: library export callbacks
    add_to_library: Optional[Callable] = None  # (items) -> None
    add_not_found: Optional[Callable] = None  # (item) -> None
    batch_add: Optional[Callable] = None  # (list[target_id]) -> None
    fetch_existing_ids: Optional[Callable] = None  # async () -> Set[id], None to skip

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
        if config.fetch_existing_ids:
            existing_ids = await config.fetch_existing_ids()
            logger.info(f"Found {len(existing_ids)} existing {config.item_type}s on target")
        else:
            existing_ids = set()
            logger.info(f"Skipping existing {config.item_type}s check")

        # Add to library export if available
        if config.add_to_library:
            config.add_to_library(source_items)

        # Phase 2: Pre-filter using cache to skip already-synced items
        items_to_search = []
        skipped = 0
        for item in source_items:
            source_id = config.get_source_id(item)
            cached_id = config.get_cache_match(source_id)
            if cached_id and cached_id in existing_ids:
                skipped += 1
            else:
                items_to_search.append(item)

        if skipped:
            logger.info(
                f"Skipped {skipped} {config.item_type}s already synced, "
                f"{len(items_to_search)} to process"
            )

        # Phase 3: Search and collect results
        added = 0
        not_found = 0
        not_found_items = []
        items_to_add = []

        for item in engine._progress_iter(items_to_search, config.progress_desc, phase="searching"):
            source_id = config.get_source_id(item)
            from_cache = config.get_cache_match(source_id) is not None

            target_id = await config.search_item(item)

            if target_id:
                if target_id in existing_ids:
                    skipped += 1
                    engine._report_progress(event="item", matched=True, from_cache=from_cache)
                    continue  # Already exists (found via search, not cache)

                items_to_add.append((target_id, item))
                engine._report_progress(event="item", matched=True, from_cache=from_cache)
            else:
                not_found += 1
                item_name = _get_item_name(item, config.item_type)
                not_found_items.append(item_name)
                engine._report_progress(event="item", matched=False)
                if config.add_not_found:
                    config.add_not_found(item)

        # Phase 4: Batch add all found items
        if items_to_add:
            logger.info(f"Adding {len(items_to_add)} {config.item_type}s...")
            if config.batch_add:
                # Use batch add (e.g., Apple Music supports adding 100 at a time)
                all_ids = [tid for tid, _ in items_to_add]
                try:
                    await retry_async_call(config.batch_add, all_ids)
                    added = len(items_to_add)
                    for _, item in items_to_add:
                        item_name = _get_item_name(item, config.item_type)
                        logger.info(f"  + Added: {item_name}")
                except Exception as e:
                    logger.warning(f"Batch add failed: {e}, falling back to one-by-one")
                    for target_id, item in items_to_add:
                        try:
                            await retry_async_call(config.add_item, target_id)
                            added += 1
                            item_name = _get_item_name(item, config.item_type)
                            logger.info(f"  + Added: {item_name}")
                        except Exception as e2:
                            logger.warning(f"Failed to add {config.item_type}: {e2}")
            else:
                for target_id, item in items_to_add:
                    try:
                        await retry_async_call(config.add_item, target_id)
                        added += 1
                        item_name = _get_item_name(item, config.item_type)
                        logger.info(f"  + Added: {item_name}")
                    except Exception as e:
                        logger.warning(f"Failed to add {config.item_type}: {e}")
                        engine._report_progress(event="item", matched=False, failed=True)

        logger.info(
            f"{config.item_type.title()}s: {added} added, "
            f"{skipped} already existed, {not_found} not found"
        )
        _log_not_found(engine, config.item_type, not_found_items)
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
        if config.fetch_existing_ids:
            existing_ids = await config.fetch_existing_ids()
            logger.info(f"Found {len(existing_ids)} existing {config.item_type}s on target")
        else:
            existing_ids = set()
            logger.info(f"Skipping existing {config.item_type}s check")

        # Add to library export if available
        if config.add_to_library:
            config.add_to_library(source_items)

        # Phase 2: Search and collect items to add
        items_to_add = []
        not_found_count = 0
        not_found_items = []

        for item in engine._progress_iter(source_items, config.progress_desc, phase="searching"):
            source_id = config.get_source_id(item)
            from_cache = config.get_cache_match(source_id) is not None

            target_id = await config.search_item(item)

            if target_id:
                if target_id not in existing_ids:
                    items_to_add.append(target_id)
                engine._report_progress(event="item", matched=True, from_cache=from_cache)
            else:
                not_found_count += 1
                not_found_items.append(_get_item_name(item, config.item_type))
                engine._report_progress(event="item", matched=False)
                if config.add_not_found:
                    config.add_not_found(item)

        # Phase 3: Add in batches
        added = 0
        if items_to_add:
            batches = [
                items_to_add[i : i + batch_size] for i in range(0, len(items_to_add), batch_size)
            ]
            for batch in engine._progress_iter(
                batches, f"Adding {config.item_type}s", phase="adding"
            ):
                try:
                    await retry_async_call(batch_add, batch)
                    added += len(batch)
                except Exception as e:
                    logger.warning(f"Failed to add batch: {e}")

        logger.info(f"Added {added} {config.item_type}s, {not_found_count} not found")
        _log_not_found(engine, config.item_type, not_found_items)
        return added, not_found_count

    finally:
        engine.rate_limiter.stop()
