"""Papers With Code API client."""

from __future__ import annotations

import httpx

from shared.cache import search_cache
from shared.rate_limiter import paperswithcode_limiter

BASE_URL = "https://paperswithcode.com/api/v1"


class PapersWithCodeClient:
    """Fetch dataset and repository hints from Papers With Code."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=25.0)

    async def fetch_datasets(self, query: str, limit: int = 5) -> list[dict]:
        cache_key = search_cache._make_key("pwc_datasets", query, limit)

        async def _fetch() -> list[dict]:
            if not query.strip():
                return []
            async with paperswithcode_limiter:
                resp = await self._client.get(f"{BASE_URL}/datasets/", params={"q": query, "page_size": limit})
            if resp.status_code >= 500:
                return []
            resp.raise_for_status()
            payload = resp.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            normalized: list[dict] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "name": item.get("name") or "",
                        "description": item.get("description") or "",
                        "url": item.get("url_abs") or item.get("url") or "",
                    }
                )
            return normalized[:limit]

        return await search_cache.get_or_set(cache_key, _fetch)

    async def fetch_repositories(self, query: str, limit: int = 5) -> list[dict]:
        cache_key = search_cache._make_key("pwc_repos", query, limit)

        async def _fetch() -> list[dict]:
            if not query.strip():
                return []
            async with paperswithcode_limiter:
                resp = await self._client.get(f"{BASE_URL}/repositories/", params={"q": query, "page_size": limit})
            if resp.status_code >= 500:
                return []
            resp.raise_for_status()
            payload = resp.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            normalized: list[dict] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "name": item.get("name") or "",
                        "url": item.get("url") or "",
                        "framework": item.get("framework") or "",
                    }
                )
            return normalized[:limit]

        return await search_cache.get_or_set(cache_key, _fetch)

    async def close(self) -> None:
        await self._client.aclose()
