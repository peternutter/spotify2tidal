"""
Async rate limiter using leaky bucket algorithm.
"""

import asyncio
from typing import Optional


class RateLimiter:
    """Async rate limiter using leaky bucket algorithm."""

    def __init__(self, max_concurrent: int = 10, rate_per_second: float = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate = rate_per_second
        self._task: Optional[asyncio.Task] = None

    async def _leak(self):
        """Periodically release from semaphore."""
        sleep_time = 1.0 / self.rate
        while True:
            await asyncio.sleep(sleep_time)
            try:
                self.semaphore.release()
            except ValueError:
                pass  # Already at max

    def start(self):
        """Start the rate limiter."""
        if not self._task:
            self._task = asyncio.create_task(self._leak())

    def stop(self):
        """Stop the rate limiter."""
        if self._task:
            self._task.cancel()
            self._task = None

    async def acquire(self):
        """Acquire a slot."""
        await self.semaphore.acquire()
