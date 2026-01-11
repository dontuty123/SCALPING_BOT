"""
Lightweight retry utility with exponential backoff.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Tuple, TypeVar

from infra.logger import get_logger

T = TypeVar("T")


def retry(
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    retry_on: Tuple[type[BaseException], ...] = (Exception,),
):
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Number of retry attempts before raising.
        backoff_factor: Initial sleep duration in seconds; doubles each retry.
        retry_on: Exception types that trigger a retry.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        logger = get_logger(f"{func.__module__}.{func.__name__}")

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = backoff_factor
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:  # type: ignore[misc]
                    attempt += 1
                    if attempt > max_retries:
                        logger.error("Retry exhausted after %s attempts: %s", attempt - 1, exc)
                        raise
                    logger.warning("Retrying attempt %s/%s after error: %s", attempt, max_retries, exc)
                    time.sleep(delay)
                    delay *= 2

        return wrapper

    return decorator

