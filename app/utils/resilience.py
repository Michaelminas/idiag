"""Resilience utilities for graceful degradation."""

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Exceptions that indicate infrastructure/network issues (should fallback)
_TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
    IOError,
)


def with_fallback(default: Any = None, log_message: str = ""):
    """Decorator that returns a default value on transient failures.

    Programming errors (TypeError, ValueError, KeyError) are NOT caught
    because they indicate bugs that should be fixed, not retried.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except _TRANSIENT_EXCEPTIONS as e:
                msg = log_message or f"{func.__name__} failed"
                logger.warning("%s: %s", msg, e)
                return default

        return wrapper

    return decorator
