"""Web search client facade (Tavily/OpenAI-web compatible wrappers)."""

from __future__ import annotations

import os

import httpx

from shared.cache import search_cache
from shared.external.types import WebSearchResult
from shared.rate_limiter import web_search_limiter


class WebSearchClient:
    """Simple web search wrapper.

    The client prefers Tavily when a key is configured and degrades gracefully
    to empty results if no provider keys are present.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None, tavily_api_key: str | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=25.0)
        self._tavily_key = tavily_api_key or os.environ.get("TAVILY_API_KEY", "")
        self.is_configured = bool(self._tavily_key)

    async def search(self, query: str, max_results: int = 5, allowed_domains: list[str] | None = None) -> list[WebSearchResult]:
        if not self.is_configured:
            return []
        cache_key = search_cache._make_key("web_search", query, max_results, ",".join(allowed_domains or []))

        async def _fetch() -> list[WebSearchResult]:
            async with web_search_limiter:
                payload = {
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                }
                if allowed_domains:
                    payload["include_domains"] = allowed_domains
                resp = await self._client.post(
                    "https://api.tavily.com/search",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._tavily_key}"},
                )
            if resp.status_code >= 500:
                return []
            resp.raise_for_status()
            raw = resp.json()
            results = raw.get("results", []) if isinstance(raw, dict) else []
            normalized: list[WebSearchResult] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    WebSearchResult(
                        title=item.get("title") or "",
                        url=item.get("url") or "",
                        content=item.get("content") or "",
                        published_date=item.get("published_date"),
                        source="tavily",
                    )
                )
            return normalized[:max_results]

        return await search_cache.get_or_set(cache_key, _fetch)

    async def close(self) -> None:
        await self._client.aclose()
