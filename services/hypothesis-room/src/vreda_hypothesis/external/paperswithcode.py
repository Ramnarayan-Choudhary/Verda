"""
Papers With Code API helper for retrieving benchmarks + repositories.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from vreda_hypothesis.utils.cache import search_cache
from vreda_hypothesis.utils.rate_limiter import paperswithcode_limiter

logger = structlog.get_logger(__name__)


BASE_URL = "https://paperswithcode.com/api/v1"


class PapersWithCodeClient:
    """Fetch datasets, benchmarks, and repository links."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def fetch_datasets(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for datasets/benchmarks matching the query."""
        cache_key = f"pwc:datasets:{query}:{limit}"

        async def _fetch() -> list[dict[str, Any]]:
            async with paperswithcode_limiter:
                params = {"q": query, "page": 1}
                url = f"{BASE_URL}/datasets/"
                resp = await self._client.get(url, params=params)
                if resp.status_code in (404, 429):
                    logger.warning("paperswithcode.datasets_skipped", status=resp.status_code, query=query[:80])
                    return []
                if resp.status_code >= 500:
                    logger.warning("paperswithcode.datasets_upstream_error", status=resp.status_code, query=query[:80])
                    return []
                resp.raise_for_status()
                content_type = (resp.headers.get("content-type") or "").lower()
                if "application/json" not in content_type:
                    logger.warning(
                        "paperswithcode.datasets_non_json",
                        query=query[:80],
                        status=resp.status_code,
                        content_type=content_type,
                    )
                    return []
                data = resp.json()
                results = data.get("results", [])[:limit] if isinstance(data, dict) else []
                return [
                    {
                        "name": item.get("name"),
                        "description": item.get("description"),
                        "papers": item.get("paper_set", []),
                        "url": item.get("url"),
                    }
                    for item in results
                ]

        return await search_cache.get_or_set(cache_key, _fetch)

    async def fetch_repositories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for code repositories referencing the query."""
        cache_key = f"pwc:repos:{query}:{limit}"

        async def _fetch() -> list[dict[str, Any]]:
            async with paperswithcode_limiter:
                params = {"q": query, "page": 1}
                url = f"{BASE_URL}/repositories/"
                resp = await self._client.get(url, params=params)
                if resp.status_code in (404, 429):
                    logger.warning("paperswithcode.repositories_skipped", status=resp.status_code, query=query[:80])
                    return []
                if resp.status_code >= 500:
                    logger.warning(
                        "paperswithcode.repositories_upstream_error",
                        status=resp.status_code,
                        query=query[:80],
                    )
                    return []
                resp.raise_for_status()
                content_type = (resp.headers.get("content-type") or "").lower()
                if "application/json" not in content_type:
                    logger.warning(
                        "paperswithcode.repositories_non_json",
                        query=query[:80],
                        status=resp.status_code,
                        content_type=content_type,
                    )
                    return []
                data = resp.json()
                results = data.get("results", [])[:limit] if isinstance(data, dict) else []
                return [
                    {
                        "name": item.get("name"),
                        "framework": item.get("framework"),
                        "stars": item.get("stars"),
                        "url": item.get("url"),
                    }
                    for item in results
                ]

        return await search_cache.get_or_set(cache_key, _fetch)

    async def close(self) -> None:
        await self._client.aclose()
