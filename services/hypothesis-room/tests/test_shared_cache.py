from __future__ import annotations

import pytest

from shared.cache import AsyncTTLCache


@pytest.mark.asyncio
async def test_async_ttl_cache_roundtrip() -> None:
    cache = AsyncTTLCache(ttl_seconds=60, max_size=10)
    key = cache._make_key("x", "a")
    assert await cache.get(key) is None
    await cache.set(key, {"ok": True})
    assert await cache.get(key) == {"ok": True}
