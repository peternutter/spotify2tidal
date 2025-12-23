"""
Retry utilities for handling transient connection errors.

Provides decorators and helpers for retrying API calls with exponential backoff.
"""

import asyncio
import functools
import logging
import random
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)

# Exceptions that indicate transient network issues worth retrying
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    ConnectionResetError,
    TimeoutError,
    OSError,  # Catches various socket errors
)


def is_retryable_error(exc: Exception) -> bool:
    """Check if an exception should trigger a retry."""
    # Direct match
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True

    # Check for wrapped exceptions (e.g., from requests/urllib3)
    error_str = str(exc).lower()
    retryable_patterns = [
        "connection reset",
        "connection aborted",
        "connection refused",
        "timed out",
        "timeout",
        "temporary failure",
        "name resolution",
        "broken pipe",
    ]
    return any(pattern in error_str for pattern in retryable_patterns)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
):
    """
    Decorator for retrying synchronous functions on transient failures.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to prevent thundering herd
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not is_retryable_error(e) or attempt == max_attempts:
                        raise

                    last_exception = e
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)

                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Retry {attempt}/{max_attempts} for {func.__name__} "
                        f"after {delay:.1f}s due to: {e}"
                    )

                    import time

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


def async_with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
):
    """
    Decorator for retrying async functions on transient failures.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to prevent thundering herd
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if not is_retryable_error(e) or attempt == max_attempts:
                        raise

                    last_exception = e
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)

                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Retry {attempt}/{max_attempts} for {func.__name__} "
                        f"after {delay:.1f}s due to: {e}"
                    )

                    await asyncio.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


async def retry_async_call(
    func: Callable,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    **kwargs,
):
    """
    Retry a synchronous function called via asyncio.to_thread.

    This is useful for wrapping tidalapi calls that are run in a thread pool.
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as e:
            if not is_retryable_error(e) or attempt == max_attempts:
                raise

            last_exception = e
            delay = base_delay * (2 ** (attempt - 1)) * (0.5 + random.random())

            func_name = getattr(func, "__name__", str(func))
            logger.warning(
                f"Retry {attempt}/{max_attempts} for {func_name} " f"after {delay:.1f}s due to: {e}"
            )

            await asyncio.sleep(delay)

    raise last_exception
