import asyncio

from spotify2tidal import retry_utils


def test_is_retryable_error_matches_patterns():
    assert retry_utils.is_retryable_error(RuntimeError("connection reset by peer"))
    assert retry_utils.is_retryable_error(RuntimeError("Timed out while reading"))
    assert not retry_utils.is_retryable_error(RuntimeError("bad request"))


def test_with_retry_retries_then_succeeds(monkeypatch):
    # Make retry timing deterministic and fast
    monkeypatch.setattr(retry_utils.random, "random", lambda: 0.0)

    import time

    sleeps = []

    def _sleep(seconds: float):
        sleeps.append(seconds)

    monkeypatch.setattr(time, "sleep", _sleep)

    attempts = {"n": 0}

    @retry_utils.with_retry(max_attempts=3, base_delay=0.1, jitter=True)
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise ConnectionError("temporary")
        return "ok"

    assert flaky() == "ok"
    assert attempts["n"] == 2
    assert len(sleeps) == 1


def test_async_with_retry_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(retry_utils.random, "random", lambda: 0.0)

    sleeps = []

    async def _sleep(seconds: float):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _sleep)

    attempts = {"n": 0}

    @retry_utils.async_with_retry(max_attempts=3, base_delay=0.1, jitter=True)
    async def flaky_async():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise TimeoutError("temporary")
        return "ok"

    async def _run():
        assert await flaky_async() == "ok"

    asyncio.run(_run())
    assert attempts["n"] == 2
    assert len(sleeps) == 1
