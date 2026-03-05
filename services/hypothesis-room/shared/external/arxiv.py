"""arXiv API client for metadata retrieval and PDF downloads."""

from __future__ import annotations

import tempfile
from pathlib import Path
from xml.etree import ElementTree

import httpx
import structlog

from shared.cache import paper_cache
from shared.external.types import PaperMetadata
from shared.rate_limiter import arxiv_limiter

logger = structlog.get_logger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "VREDA.ai/hypothesis-shared"


class ArxivClient:
    """Client for arXiv metadata and PDF retrieval."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    @staticmethod
    def normalize_id(arxiv_id: str) -> str:
        if not arxiv_id:
            raise ValueError("arxiv_id is required")
        cleaned = arxiv_id.replace("arXiv:", "").strip()
        if "v" in cleaned:
            cleaned = cleaned.split("v")[0]
        return cleaned

    async def fetch_metadata(self, arxiv_id: str) -> PaperMetadata:
        normalized = self.normalize_id(arxiv_id)
        cache_key = paper_cache._make_key("arxiv_metadata", normalized)

        async def _fetch() -> PaperMetadata:
            async with arxiv_limiter:
                resp = await self._client.get(
                    ARXIV_API,
                    params={"id_list": normalized},
                    headers={"User-Agent": USER_AGENT},
                )
            resp.raise_for_status()
            return self._parse_metadata(resp.text, normalized)

        return await paper_cache.get_or_set(cache_key, _fetch)

    async def search(self, query: str, max_results: int = 10) -> list[PaperMetadata]:
        cache_key = paper_cache._make_key("arxiv_search", query, max_results)

        async def _search() -> list[PaperMetadata]:
            async with arxiv_limiter:
                resp = await self._client.get(
                    ARXIV_API,
                    params={
                        "search_query": f"all:{query}",
                        "max_results": max_results,
                        "sortBy": "relevance",
                    },
                    headers={"User-Agent": USER_AGENT},
                )
            resp.raise_for_status()
            return self._parse_search_results(resp.text)

        return await paper_cache.get_or_set(cache_key, _search)

    async def download_pdf(self, arxiv_id: str, destination: Path | None = None) -> Path:
        normalized = self.normalize_id(arxiv_id)
        url = f"https://arxiv.org/pdf/{normalized}.pdf"
        async with arxiv_limiter:
            resp = await self._client.get(url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()

        if destination is None:
            _, tmp = tempfile.mkstemp(prefix=f"arxiv_{normalized}_", suffix=".pdf")
            destination = Path(tmp)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(resp.content)
        return destination

    def _parse_metadata(self, payload: str, arxiv_id: str) -> PaperMetadata:
        entries = self._parse_entries(payload)
        if not entries:
            raise ValueError(f"No entry found for {arxiv_id}")
        item = entries[0]
        item.arxiv_id = arxiv_id
        return item

    def _parse_search_results(self, payload: str) -> list[PaperMetadata]:
        return self._parse_entries(payload)

    @staticmethod
    def _parse_entries(payload: str) -> list[PaperMetadata]:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ElementTree.fromstring(payload)
        results: list[PaperMetadata] = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            abstract = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:4]
            year = int(published) if published.isdigit() else None
            id_url = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            arxiv_id = id_url.split("/abs/")[-1] if "/abs/" in id_url else None
            if arxiv_id and "v" in arxiv_id:
                arxiv_id = arxiv_id.split("v")[0]
            authors = [
                (author.findtext("atom:name", default="", namespaces=ns) or "").strip()
                for author in entry.findall("atom:author", ns)
            ]
            pdf_link = entry.find("atom:link[@title='pdf']", ns)
            url = pdf_link.get("href") if pdf_link is not None else (f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else "")
            results.append(
                PaperMetadata(
                    title=title,
                    arxiv_id=arxiv_id,
                    authors=[a for a in authors if a],
                    abstract=abstract,
                    year=year,
                    venue="arXiv",
                    url=url,
                )
            )
        return results

    async def close(self) -> None:
        await self._client.aclose()
