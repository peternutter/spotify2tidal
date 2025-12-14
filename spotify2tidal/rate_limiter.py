"""
Async rate limiter with bounded concurrency and request pacing.
"""

import asyncio


class RateLimiter:
    """
    Rate limiter that combines:
    - **Concurrency limiting** via a semaphore
    - **Request pacing** to a maximum rate (requests/second)

    Notes:
    - This limiter is designed to be *bounded* (no unbounded permit growth).
    - `start()` / `stop()` are kept as no-ops for backwards compatibility.
    """

    def __init__(self, max_concurrent: int = 10, rate_per_second: float = 10):
        self.semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self.rate = float(rate_per_second) if rate_per_second else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed: float = 0.0

    def start(self):
        """Backward-compatible no-op."""
        return

    def stop(self):
        """Backward-compatible no-op."""
        return

    async def acquire(self):
        """
        Acquire a concurrency slot and wait until the next paced request slot.
        """
        await self.semaphore.acquire()

        if self.rate <= 0:
            return

        interval = 1.0 / self.rate
        loop = asyncio.get_running_loop()

        async with self._lock:
            now = loop.time()
            wait_for = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + interval

        if wait_for > 0:
            await asyncio.sleep(wait_for)

    def release(self):
        """Release a previously acquired concurrency slot."""
        try:
            self.semaphore.release()
        except ValueError:
            # Shouldn't happen, but don't crash if release is mismatched.
            pass
