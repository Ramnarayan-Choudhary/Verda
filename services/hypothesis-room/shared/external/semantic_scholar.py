"""Semantic Scholar Graph API client."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import httpx
import structlog

from shared.cache import paper_cache, search_cache
from shared.external.types import PaperMetadata
from shared.rate_limiter import semantic_scholar_limiter

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarClient:
    """Wrapper around the Semantic Scholar Graph API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None, api_key: str = "") -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
        self._headers = {"x-api-key": key} if key else {}

    async def fetch_paper(self, arxiv_id: str) -> PaperMetadata | None:
        cache_key = paper_cache._make_key("s2_paper", arxiv_id)

        async def _fetch() -> PaperMetadata | None:
            async with semantic_scholar_limiter:
                resp = await self._client.get(
                    f"{BASE_URL}/paper/arXiv:{arxiv_id}",
                    params={"fields": "title,abstract,authors,year,citationCount,url,externalIds"},
                    headers=self._headers,
                )
            if resp.status_code in (404, 429) or resp.status_code >= 500:
                return None
            resp.raise_for_status()
            return self._to_metadata(resp.json())

        return await paper_cache.get_or_set(cache_key, _fetch)

    async def fetch_related(self, identifier: str, limit: int = 30) -> list[PaperMetadata]:
        cache_key = search_cache._make_key("s2_related", identifier, limit)

        async def _fetch() -> list[PaperMetadata]:
            paper_path = self._resolve_identifier(identifier)
            if not paper_path:
                return await self.keyword_search(identifier, limit=min(limit, 10))

            params = {"fields": "title,abstract,authors,year,citationCount,url,externalIds", "limit": limit}

            async def _request(url: str) -> list[PaperMetadata]:
                async with semantic_scholar_limiter:
                    resp = await self._client.get(url, params=params, headers=self._headers)
                if resp.status_code in (404, 429) or resp.status_code >= 500:
                    return []
                resp.raise_for_status()
                payload = resp.json()
                papers: list[PaperMetadata] = []
                for item in payload.get("data", []):
                    if not item:
                        continue
                    raw = item.get("citedPaper") or item.get("citingPaper")
                    try:
                        papers.append(self._to_metadata(raw))
                    except Exception:
                        continue
                return papers

            refs, cites = await asyncio.gather(
                _request(f"{BASE_URL}/paper/{paper_path}/references"),
                _request(f"{BASE_URL}/paper/{paper_path}/citations"),
            )
            merged: dict[str, PaperMetadata] = {}
            for paper in refs + cites:
                key = (paper.arxiv_id or "").lower() or (paper.semantic_scholar_id or "").lower() or paper.title.lower()
                if key:
                    merged[key] = paper
            return list(merged.values())[:limit]

        return await search_cache.get_or_set(cache_key, _fetch)

    async def keyword_search(self, query: str, limit: int = 5) -> list[PaperMetadata]:
        cache_key = search_cache._make_key("s2_search", query, limit)

        async def _search() -> list[PaperMetadata]:
            async with semantic_scholar_limiter:
                resp = await self._client.get(
                    f"{BASE_URL}/paper/search",
                    params={"query": query, "limit": limit, "fields": "title,abstract,year,authors,url,externalIds,citationCount"},
                    headers=self._headers,
                )
            if resp.status_code in (429,) or resp.status_code >= 500:
                return []
            resp.raise_for_status()
            papers: list[PaperMetadata] = []
            for paper in resp.json().get("data", []):
                try:
                    papers.append(self._to_metadata(paper))
                except Exception:
                    continue
            return papers

        return await search_cache.get_or_set(cache_key, _search)

    @staticmethod
    def _resolve_identifier(identifier: str) -> str:
        text = identifier.strip()
        if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", text):
            return f"arXiv:{text}"
        if re.match(r"^[0-9a-f]{40}$", text):
            return text
        return ""

    @staticmethod
    def _to_metadata(payload: dict[str, Any] | None) -> PaperMetadata:
        if not payload:
            return PaperMetadata(title="Unknown")

        external_ids = payload.get("externalIds") or {}
        if not isinstance(external_ids, dict):
            external_ids = {}

        arxiv_id = external_ids.get("ArXiv")
        if isinstance(arxiv_id, str):
            arxiv_id = arxiv_id.strip() or None
        else:
            arxiv_id = None

        year = payload.get("year")
        if isinstance(year, str) and year.isdigit():
            year = int(year)
        elif not isinstance(year, int):
            year = None

        authors = [
            item.get("name", "").strip()
            for item in (payload.get("authors") or [])
            if isinstance(item, dict) and item.get("name")
        ]

        citation_count = payload.get("citationCount")
        if not isinstance(citation_count, int):
            citation_count = 0

        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            title = "Unknown"

        abstract = payload.get("abstract")
        if not isinstance(abstract, str):
            abstract = ""

        return PaperMetadata(
            title=title,
            arxiv_id=arxiv_id,
            semantic_scholar_id=payload.get("paperId"),
            authors=authors,
            abstract=abstract,
            year=year,
            citation_count=citation_count,
            venue="Semantic Scholar",
            url=payload.get("url") or "",
        )

    async def close(self) -> None:
        await self._client.aclose()
