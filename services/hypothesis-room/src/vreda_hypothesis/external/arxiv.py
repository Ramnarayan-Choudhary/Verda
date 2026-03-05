"""
Async arXiv API helper (Stage 1 ingestion + Stage 2 grounding).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from xml.etree import ElementTree

import httpx
import structlog

from vreda_hypothesis.models import PaperMetadata
from vreda_hypothesis.utils.cache import paper_cache
from vreda_hypothesis.utils.rate_limiter import arxiv_limiter

logger = structlog.get_logger(__name__)


ARXIV_API = "https://export.arxiv.org/api/query"


class ArxivClient:
    """Fetch paper metadata and PDFs directly from arXiv."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    @staticmethod
    def normalize_id(arxiv_id: str) -> str:
        """Normalize an arXiv ID (strip arXiv: prefix + version)."""
        if not arxiv_id:
            raise ValueError("arxiv_id is required")
        arxiv_id = arxiv_id.replace("arXiv:", "").strip()
        if "v" in arxiv_id:
            arxiv_id = arxiv_id.split("v")[0]
        return arxiv_id

    async def fetch_metadata(self, arxiv_id: str) -> PaperMetadata:
        """Fetch metadata via the arXiv Atom API."""
        normalized = self.normalize_id(arxiv_id)
        cache_key = f"arxiv:{normalized}"

        async def _fetch() -> PaperMetadata:
            async with arxiv_limiter:
                params = {"id_list": normalized}
                resp = await self._client.get(ARXIV_API, params=params, headers={"User-Agent": "VREDA.ai/1.0"})
                resp.raise_for_status()
                return self._parse_metadata(resp.text, normalized)

        return await paper_cache.get_or_set(cache_key, _fetch)

    def _parse_metadata(self, payload: str, arxiv_id: str) -> PaperMetadata:
        """Parse Atom XML payload into PaperMetadata."""
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ElementTree.fromstring(payload)
        entry = root.find("atom:entry", ns)
        if entry is None:
            raise ValueError(f"No entry found for {arxiv_id}")

        def _text(tag: str) -> str:
            node = entry.find(f"atom:{tag}", ns)
            return node.text.strip() if node is not None and node.text else ""

        title = _text("title")
        abstract = _text("summary")
        published = _text("published")[:4]
        year = int(published) if published.isdigit() else None
        authors = [author.findtext("atom:name", default="", namespaces=ns) for author in entry.findall("atom:author", ns)]
        pdf_url = entry.find("atom:link[@title='pdf']", ns)
        url = pdf_url.get("href") if pdf_url is not None else f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        metadata = PaperMetadata(
            title=title,
            arxiv_id=arxiv_id,
            semantic_scholar_id=None,
            authors=[a for a in authors if a],
            abstract=abstract,
            year=year,
            citation_count=0,
            venue="arXiv",
            url=url,
        )
        logger.info("arxiv.metadata_fetched", arxiv_id=arxiv_id, title=title)
        return metadata

    async def download_pdf(self, arxiv_id: str, destination: Path | None = None) -> Path:
        """Download the PDF for an arXiv paper."""
        normalized = self.normalize_id(arxiv_id)
        pdf_url = f"https://arxiv.org/pdf/{normalized}.pdf"
        async with arxiv_limiter:
            resp = await self._client.get(pdf_url, headers={"User-Agent": "VREDA.ai/1.0"})
            resp.raise_for_status()

        if destination is None:
            fd, tmp = tempfile.mkstemp(prefix=f"arxiv_{normalized}_", suffix=".pdf")
            destination = Path(tmp)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)

        destination.write_bytes(resp.content)
        logger.info("arxiv.pdf_downloaded", arxiv_id=arxiv_id, path=str(destination))
        return destination

    async def close(self) -> None:
        await self._client.aclose()
