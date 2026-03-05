"""
Async API response caching — prevents redundant external API calls.

Uses a simple in-memory TTL cache. Paper-level caching since
the same paper metadata is queried multiple times across stages.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AsyncCache:
    """Thread-safe TTL cache for async API responses."""

    def __init__(self, ttl_seconds: int = 900, max_size: int = 1000) -> None:
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(prefix: str, *args: Any) -> str:
        """Create a deterministic cache key."""
        raw = f"{prefix}:{':'.join(str(a) for a in args)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def get(self, key: str) -> Any | None:
        """Get a cached value if it exists and hasn't expired."""
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    self._hits += 1
                    return value
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    async def set(self, key: str, value: Any) -> None:
        """Store a value in the cache."""
        async with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]

            self._cache[key] = (value, time.time() + self._ttl)

    async def get_or_set(self, key: str, factory) -> Any:
        """Get from cache or compute and store.

        Args:
            key: Cache key.
            factory: Async callable that produces the value.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set(key, value)
        return value

    def stats(self) -> dict:
        """Return cache hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 2) if total > 0 else 0,
            "size": len(self._cache),
        }

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()


# Singleton caches for external APIs
paper_cache = AsyncCache(ttl_seconds=1800, max_size=500)    # 30 min
search_cache = AsyncCache(ttl_seconds=900, max_size=200)    # 15 min
embedding_cache = AsyncCache(ttl_seconds=3600, max_size=100)  # 1 hr
