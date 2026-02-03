"""Rate limiting and retry utilities for API calls."""

import time
import random
from functools import wraps
from typing import Callable, Any, Optional


class RateLimitConfig:
    """Configuration for rate limiting."""

    # Gemini 3 Flash limits
    TPM_LIMIT = 1_000_000  # 1M tokens per minute
    RPM_LIMIT = 2000       # Requests per minute (typical)

    # Retry settings
    MAX_RETRIES = 3
    BASE_DELAY = 2.0       # Base delay in seconds
    MAX_DELAY = 60.0       # Max delay in seconds
    JITTER = 0.5           # Random jitter factor


def retry_with_backoff(
    max_retries: int = RateLimitConfig.MAX_RETRIES,
    base_delay: float = RateLimitConfig.BASE_DELAY,
    max_delay: float = RateLimitConfig.MAX_DELAY,
    retryable_errors: tuple = (429, 503, 500),
):
    """Decorator to retry API calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay between retries in seconds.
        max_delay: Maximum delay between retries.
        retryable_errors: HTTP status codes that should trigger retry.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e)

                    # Check if error is retryable
                    is_retryable = any(
                        str(code) in error_str or
                        "RESOURCE_EXHAUSTED" in error_str or
                        "UNAVAILABLE" in error_str or
                        "overloaded" in error_str.lower()
                        for code in retryable_errors
                    )

                    if not is_retryable or attempt == max_retries:
                        raise

                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        base_delay * (2 ** attempt),
                        max_delay
                    )
                    jitter = delay * RateLimitConfig.JITTER * random.random()
                    actual_delay = delay + jitter

                    print(f"⚠️ API error (attempt {attempt + 1}/{max_retries + 1}), "
                          f"retrying in {actual_delay:.1f}s...")
                    time.sleep(actual_delay)

            raise last_exception

        return wrapper
    return decorator


def add_delay_between_calls(delay: float = 0.5):
    """Decorator to add delay after function execution.

    Args:
        delay: Delay in seconds after each call.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            time.sleep(delay)
            return result
        return wrapper
    return decorator


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, tokens_per_minute: int = RateLimitConfig.TPM_LIMIT):
        """Initialize token bucket.

        Args:
            tokens_per_minute: Maximum tokens allowed per minute.
        """
        self.capacity = tokens_per_minute
        self.tokens = tokens_per_minute
        self.last_refill = time.time()
        self.refill_rate = tokens_per_minute / 60.0  # tokens per second

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now

    def consume(self, tokens: int) -> bool:
        """Try to consume tokens.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            True if tokens were consumed, False if not enough tokens.
        """
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_for_tokens(self, tokens: int):
        """Wait until enough tokens are available.

        Args:
            tokens: Number of tokens needed.
        """
        self._refill()
        if self.tokens < tokens:
            wait_time = (tokens - self.tokens) / self.refill_rate
            print(f"⏳ Rate limit: waiting {wait_time:.1f}s for tokens...")
            time.sleep(wait_time)
            self._refill()
        self.tokens -= tokens
