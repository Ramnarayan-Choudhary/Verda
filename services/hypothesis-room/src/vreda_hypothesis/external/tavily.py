"""
Tavily Search API client — web search for literature discovery.

Finds papers, blog posts, and technical content that Semantic Scholar
and arXiv APIs miss: workshop papers, preprints on personal sites,
technical blog posts, papers behind paywalls via snippets.

Used by open_deep_research (LangChain) for iterative research.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from vreda_hypothesis.config import settings
from vreda_hypothesis.utils.rate_limiter import AsyncRateLimiter

logger = structlog.get_logger(__name__)

# Tavily rate limit: ~2 req/sec to stay safe on free tier
tavily_limiter = AsyncRateLimiter(rate=2, period=1.0, name="tavily")

TAVILY_API_URL = "https://api.tavily.com"


class TavilySearchClient:
    """Async Tavily Search API client for web-based literature discovery."""

    def __init__(self, api_key: str | None = None, http_client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key or settings.tavily_api_key
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    @property
    def is_configured(self) -> bool:
        """Check if Tavily API key is set."""
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: list[str] | None = None,
        topic: str = "general",
    ) -> list[dict[str, Any]]:
        """Search the web via Tavily API.

        Args:
            query: Search query string
            max_results: Max results to return (1-20)
            search_depth: "basic" (fast) or "advanced" (thorough, better for research)
            include_domains: Optional domain filter (e.g., ["arxiv.org", "scholar.google.com"])
            topic: "general" or "news"

        Returns:
            List of result dicts with keys: title, url, content, score
        """
        if not self._api_key:
            logger.debug("tavily.not_configured")
            return []

        try:
            async with tavily_limiter:
                payload: dict[str, Any] = {
                    "query": query,
                    "max_results": min(max_results, 10),
                    "search_depth": search_depth,
                    "topic": topic,
                    "include_answer": False,
                }
                if include_domains:
                    payload["include_domains"] = include_domains

                resp = await self._client.post(
                    f"{TAVILY_API_URL}/search",
                    json={"api_key": self._api_key, **payload},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results", [])
                logger.info(
                    "tavily.search_complete",
                    query=query[:80],
                    results=len(results),
                )
                return results

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "tavily.search_http_error",
                status=exc.response.status_code,
                query=query[:80],
            )
            return []
        except Exception as exc:
            logger.warning("tavily.search_error", error=str(exc), query=query[:80])
            return []

    async def search_papers(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search specifically for academic papers across the web.

        Targets academic domains for higher relevance.
        """
        academic_domains = [
            "arxiv.org",
            "scholar.google.com",
            "semanticscholar.org",
            "openreview.net",
            "proceedings.neurips.cc",
            "proceedings.mlr.press",
            "aclanthology.org",
            "biorxiv.org",
            "ieee.org",
            "dl.acm.org",
        ]

        return await self.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_domains=academic_domains,
        )

    async def search_broad(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Broad web search — finds blog posts, GitHub repos, technical docs,
        workshop papers, and other content that academic APIs miss.
        """
        return await self.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
        )

    async def close(self) -> None:
        await self._client.aclose()
