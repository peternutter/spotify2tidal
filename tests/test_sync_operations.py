import asyncio

from spotify2tidal.sync_operations import SyncConfig, sync_items, sync_items_batched


class _RateLimiter:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


class _Engine:
    def __init__(self):
        self.rate_limiter = _RateLimiter()
        self.events = []
        self._item_limit = None

    def _apply_limit(self, items: list) -> list:
        return items

    def _progress_iter(self, iterable, *_args, **_kwargs):
        for item in iterable:
            yield item

    def _report_progress(self, **kwargs):
        self.events.append(kwargs)


def test_sync_items_exercising_cache_skip_add_failure_and_not_found():
    engine = _Engine()

    source_items = [
        {"id": "a"},
        {"id": "b"},
        {"id": "c"},
        {"id": "d"},
    ]

    async def fetch_source():
        return list(source_items)

    async def fetch_existing_ids():
        # Make "b" appear to already exist on target
        return {200}

    async def search_item(item: dict):
        # a -> 100 (added)
        # b -> 200 (skipped because exists)
        # c -> 300 (add fails)
        # d -> None (not found)
        return {"a": 100, "b": 200, "c": 300}.get(item["id"])

    added_ids = []

    def add_item(target_id: int):
        if target_id == 300:
            raise RuntimeError("boom")
        added_ids.append(target_id)

    not_found_items = []

    def add_not_found(item: dict):
        not_found_items.append(item)

    def get_source_id(item: dict) -> str:
        return item["id"]

    def get_cache_match(source_id: str):
        # Pretend only "a" came from cache
        return 999 if source_id == "a" else None

    config = SyncConfig(
        item_type="track",
        fetch_source=fetch_source,
        fetch_existing_ids=fetch_existing_ids,
        search_item=search_item,
        get_source_id=get_source_id,
        get_cache_match=get_cache_match,
        add_item=add_item,
        add_not_found=add_not_found,
        progress_desc="Syncing tracks",
        reverse_order=False,
    )

    added, not_found = asyncio.run(sync_items(config, engine))  # type: ignore[arg-type]

    assert engine.rate_limiter.started == 1
    assert engine.rate_limiter.stopped == 1

    assert added == 1
    assert not_found == 1
    assert added_ids == [100]
    assert [i["id"] for i in not_found_items] == ["d"]

    # Verify we emitted a mix of outcomes and included from_cache on matches
    matched_events = [e for e in engine.events if e.get("event") == "item"]
    assert any(
        e.get("matched") is True and e.get("from_cache") is True for e in matched_events
    )
    assert any(
        e.get("matched") is True and e.get("from_cache") is False
        for e in matched_events
    )
    assert any(e.get("failed") is True for e in matched_events)
    assert any(e.get("matched") is False and "failed" not in e for e in matched_events)


def test_sync_items_batched_batches_and_handles_batch_failures():
    engine = _Engine()

    async def fetch_source():
        return [{"id": "a"}, {"id": "b"}, {"id": "c"}]

    async def fetch_existing_ids():
        # none exist
        return set()

    async def search_item(item: dict):
        return {"a": "s1", "b": "s2", "c": "s3"}[item["id"]]

    def get_source_id(item: dict) -> str:
        return item["id"]

    def get_cache_match(_source_id: str):
        return None

    not_found_items = []

    def add_not_found(item: dict):
        not_found_items.append(item)

    batches = []

    def batch_add(ids):
        batches.append(list(ids))
        if ids == ["s3"]:
            raise RuntimeError("boom batch")

    config = SyncConfig(
        item_type="track",
        fetch_source=fetch_source,
        fetch_existing_ids=fetch_existing_ids,
        search_item=search_item,
        get_source_id=get_source_id,
        get_cache_match=get_cache_match,
        add_item=lambda _x: None,
        add_not_found=add_not_found,
        progress_desc="Syncing tracks",
        reverse_order=False,
    )

    added, not_found = asyncio.run(
        sync_items_batched(config, engine, batch_add=batch_add, batch_size=2)  # type: ignore[arg-type]
    )

    # First batch adds 2, second batch fails and does not count
    assert batches == [["s1", "s2"], ["s3"]]
    assert added == 2
    assert not_found == 0
    assert not_found_items == []
