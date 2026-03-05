"""
Semantic Scholar Graph API client used for grounding + novelty checks.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from vreda_hypothesis.config import settings
from vreda_hypothesis.models import PaperMetadata
from vreda_hypothesis.utils.cache import paper_cache, search_cache
from vreda_hypothesis.utils.rate_limiter import semantic_scholar_limiter

logger = structlog.get_logger(__name__)


BASE_URL = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarClient:
    """Minimal wrapper around the Semantic Scholar Graph API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._headers = {"x-api-key": settings.semantic_scholar_api_key} if settings.semantic_scholar_api_key else {}

    async def fetch_paper(self, arxiv_id: str) -> PaperMetadata | None:
        """Fetch a single paper by arXiv ID."""
        cache_key = f"s2:paper:{arxiv_id}"

        async def _fetch() -> PaperMetadata | None:
            async with semantic_scholar_limiter:
                url = f"{BASE_URL}/paper/arXiv:{arxiv_id}"
                params = {
                    "fields": "title,abstract,authors,year,citationCount,publicationTypes,url,externalIds"
                }
                resp = await self._client.get(url, params=params, headers=self._headers)
                if resp.status_code == 404:
                    return None
                if resp.status_code == 429:
                    logger.warning("semantic_scholar.fetch_paper_rate_limited", arxiv_id=arxiv_id)
                    return None
                if resp.status_code >= 500:
                    logger.warning(
                        "semantic_scholar.fetch_paper_upstream_error",
                        status=resp.status_code,
                        arxiv_id=arxiv_id,
                    )
                    return None
                resp.raise_for_status()
                if "application/json" not in (resp.headers.get("content-type") or "").lower():
                    logger.warning(
                        "semantic_scholar.fetch_paper_non_json",
                        arxiv_id=arxiv_id,
                        content_type=resp.headers.get("content-type"),
                    )
                    return None
                return self._to_metadata(resp.json())

        return await paper_cache.get_or_set(cache_key, _fetch)

    def _resolve_paper_identifier(self, identifier: str) -> str:
        """Resolve identifier to an S2 API paper path segment.

        Supports:
        - arXiv IDs (e.g., "2503.08979") → "arXiv:2503.08979"
        - S2 paper IDs (40-char hex) → used as-is
        - Other strings → treated as title (not a valid S2 path, returns empty)
        """
        identifier = identifier.strip()
        if not identifier:
            return ""

        # arXiv ID pattern: YYMM.NNNNN or YYMM.NNNN (optionally with vN suffix)
        import re
        if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", identifier):
            return f"arXiv:{identifier}"

        # S2 paper ID (40-char hex)
        if re.match(r"^[0-9a-f]{40}$", identifier):
            return identifier

        # Not a recognized identifier format
        return ""

    async def fetch_related(self, identifier: str, limit: int = 30) -> list[PaperMetadata]:
        """Fetch the top related papers via references + citations.

        Accepts arXiv IDs, S2 paper IDs, or paper titles.
        For titles, falls back to keyword search since S2 graph API
        requires a specific paper ID.
        """
        cache_key = f"s2:related:{identifier}:{limit}"

        async def _fetch() -> list[PaperMetadata]:
            paper_path = self._resolve_paper_identifier(identifier)

            # If identifier is not a valid arXiv/S2 ID (e.g., it's a paper title),
            # fall back to keyword search instead of making a guaranteed-to-fail API call.
            if not paper_path:
                logger.info(
                    "semantic_scholar.fetch_related_fallback_to_search",
                    identifier=identifier[:80],
                    reason="not_a_valid_paper_id",
                )
                return await self.keyword_search(identifier, limit=min(limit, 10))

            params = {
                "fields": "title,abstract,authors,year,citationCount,url,externalIds",
                "limit": limit,
            }
            references_url = f"{BASE_URL}/paper/{paper_path}/references"
            citations_url = f"{BASE_URL}/paper/{paper_path}/citations"

            async def _request(url: str) -> list[PaperMetadata]:
                async with semantic_scholar_limiter:
                    resp = await self._client.get(url, params=params, headers=self._headers)
                    if resp.status_code in (404, 429):
                        logger.warning("semantic_scholar.fetch_related_skipped", url=url, status=resp.status_code)
                        return []
                    if resp.status_code >= 500:
                        logger.warning(
                            "semantic_scholar.fetch_related_upstream_error",
                            url=url,
                            status=resp.status_code,
                        )
                        return []
                    resp.raise_for_status()
                    if "application/json" not in (resp.headers.get("content-type") or "").lower():
                        logger.warning(
                            "semantic_scholar.fetch_related_non_json",
                            url=url,
                            content_type=resp.headers.get("content-type"),
                        )
                        return []
                    data = resp.json()
                    items = data.get("data", [])
                    papers: list[PaperMetadata] = []
                    for item in items:
                        if not item:
                            continue
                        paper_payload = item.get("citedPaper") or item.get("citingPaper")
                        try:
                            papers.append(self._to_metadata(paper_payload))
                        except Exception as exc:
                            logger.debug("semantic_scholar.fetch_related_payload_skipped", error=str(exc))
                    return papers

            references, citations = await asyncio.gather(_request(references_url), _request(citations_url))
            merged: dict[str, PaperMetadata] = {}
            for paper in references + citations:
                if not paper:
                    continue
                key = (
                    (paper.arxiv_id or "").strip().lower()
                    or (paper.semantic_scholar_id or "").strip().lower()
                    or paper.title.strip().lower()
                )
                if key:
                    merged[key] = paper
            return list(merged.values())[:limit]

        return await search_cache.get_or_set(cache_key, _fetch)

    async def keyword_search(self, query: str, limit: int = 5) -> list[PaperMetadata]:
        """Free text search for novelty scanning."""
        cache_key = f"s2:search:{query}:{limit}"

        async def _search() -> list[PaperMetadata]:
            async with semantic_scholar_limiter:
                params = {"query": query, "limit": limit, "fields": "title,abstract,year,authors,url,externalIds"}
                url = f"{BASE_URL}/paper/search"
                resp = await self._client.get(url, params=params, headers=self._headers)
                if resp.status_code == 429:
                    logger.warning("semantic_scholar.keyword_search_rate_limited", query=query[:80])
                    return []
                if resp.status_code >= 500:
                    logger.warning(
                        "semantic_scholar.keyword_search_upstream_error",
                        query=query[:80],
                        status=resp.status_code,
                    )
                    return []
                resp.raise_for_status()
                if "application/json" not in (resp.headers.get("content-type") or "").lower():
                    logger.warning(
                        "semantic_scholar.keyword_search_non_json",
                        query=query[:80],
                        content_type=resp.headers.get("content-type"),
                    )
                    return []
                data = resp.json()
                papers: list[PaperMetadata] = []
                for paper in data.get("data", []):
                    try:
                        papers.append(self._to_metadata(paper))
                    except Exception as exc:
                        logger.debug("semantic_scholar.keyword_search_payload_skipped", error=str(exc))
                return papers

        return await search_cache.get_or_set(cache_key, _search)

    def _to_metadata(self, payload: dict[str, Any] | None) -> PaperMetadata:
        if not payload:
            return PaperMetadata(title="Unknown", arxiv_id=None, semantic_scholar_id=None)

        external = payload.get("externalIds") or {}
        if not isinstance(external, dict):
            external = {}

        arxiv_id = external.get("ArXiv")
        if isinstance(arxiv_id, str):
            arxiv_id = arxiv_id.strip() or None
        else:
            arxiv_id = None

        raw_authors = payload.get("authors") or []
        if not isinstance(raw_authors, list):
            raw_authors = []

        authors: list[str] = []
        for author in raw_authors:
            if not isinstance(author, dict):
                continue
            name = author.get("name")
            if isinstance(name, str) and name.strip():
                authors.append(name.strip())

        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            title = "Unknown"

        abstract = payload.get("abstract")
        if not isinstance(abstract, str):
            abstract = ""

        year_raw = payload.get("year")
        year: int | None
        if isinstance(year_raw, int):
            year = year_raw
        elif isinstance(year_raw, str) and year_raw.isdigit():
            year = int(year_raw)
        else:
            year = None

        citation_raw = payload.get("citationCount")
        if isinstance(citation_raw, int):
            citation_count = citation_raw
        elif isinstance(citation_raw, str) and citation_raw.isdigit():
            citation_count = int(citation_raw)
        else:
            citation_count = 0

        url = payload.get("url")
        if not isinstance(url, str):
            url = ""

        semantic_id = payload.get("paperId")
        if not isinstance(semantic_id, str):
            semantic_id = None

        return PaperMetadata(
            title=title,
            arxiv_id=arxiv_id,
            semantic_scholar_id=semantic_id,
            authors=authors,
            abstract=abstract,
            year=year,
            citation_count=citation_count,
            venue="Semantic Scholar",
            url=url,
        )

    async def close(self) -> None:
        await self._client.aclose()
