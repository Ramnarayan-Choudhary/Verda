"""PDF download, text extraction, and chunking utilities."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import httpx
import structlog

from shared.rate_limiter import arxiv_limiter

logger = structlog.get_logger(__name__)


async def download_arxiv_pdf(arxiv_id: str, destination: Path | None = None) -> Path:
    """Download a PDF from arXiv by ID."""
    normalized = arxiv_id.replace("arXiv:", "").strip()
    if "v" in normalized:
        normalized = normalized.split("v")[0]

    pdf_url = f"https://arxiv.org/pdf/{normalized}.pdf"
    async with arxiv_limiter:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(pdf_url, headers={"User-Agent": "VREDA.ai/2.0"})
            resp.raise_for_status()

    if destination is None:
        fd, tmp = tempfile.mkstemp(prefix=f"arxiv_{normalized}_", suffix=".pdf")
        destination = Path(tmp)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)

    destination.write_bytes(resp.content)
    logger.info("pdf.downloaded", arxiv_id=arxiv_id, path=str(destination), size_kb=len(resp.content) // 1024)
    return destination


async def extract_text(path: Path) -> str:
    """Extract text from a PDF using PyMuPDF with block fallback."""

    def _sync_extract() -> str:
        import fitz

        def _word_count(text: str) -> int:
            return len([t for t in text.split() if t.strip()])

        def _extract_blocks(doc: fitz.Document) -> str:
            parts: list[str] = []
            for page in doc:
                blocks = page.get_text("blocks", sort=True)
                for block in blocks:
                    text = block[4] if len(block) > 4 else ""
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            return "\n".join(parts)

        with fitz.open(path) as doc:
            primary_parts: list[str] = []
            for page in doc:
                text = page.get_text("text")
                if text and text.strip():
                    primary_parts.append(text.strip())

            primary_text = "\n".join(primary_parts).strip()
            min_expected_words = max(800, len(doc) * 120)
            if _word_count(primary_text) >= min_expected_words:
                return primary_text

            fallback_text = _extract_blocks(doc).strip()
            if _word_count(fallback_text) > _word_count(primary_text):
                logger.warning(
                    "pdf.fallback_extraction_used",
                    path=str(path),
                    primary_words=_word_count(primary_text),
                    fallback_words=_word_count(fallback_text),
                )
                return fallback_text

            return primary_text

    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _sync_extract)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Sliding-window text chunker."""
    if not text:
        return []
    tokens = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(len(tokens), start + chunk_size)
        chunk = " ".join(tokens[start:end])
        chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = 0
        if end == len(tokens):
            break
    return chunks
