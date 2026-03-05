"""Async token-bucket rate limiter for external API clients."""

from __future__ import annotations

import asyncio
import time

class AsyncRateLimiter:
    """Token-bucket rate limiter for async API calls.

    Usage:
        limiter = AsyncRateLimiter(rate=10, period=1.0)
        async with limiter:
            await make_api_call()
    """

    def __init__(self, rate: int, period: float = 1.0, name: str = "default") -> None:
        self._rate = rate
        self._period = period
        self._name = name
        self._tokens = float(rate)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    float(self._rate),
                    self._tokens + elapsed * (self._rate / self._period),
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            wait_time = self._period / self._rate
            await asyncio.sleep(wait_time)

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args) -> None:
        pass


# Pre-configured limiters
arxiv_limiter = AsyncRateLimiter(rate=1, period=3.0, name="arxiv")
semantic_scholar_limiter = AsyncRateLimiter(rate=10, period=1.0, name="semantic_scholar")
paperswithcode_limiter = AsyncRateLimiter(rate=5, period=1.0, name="paperswithcode")
web_search_limiter = AsyncRateLimiter(rate=2, period=1.0, name="web_search")
