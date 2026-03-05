"""Layer 0 — Multi-Document Intelligence.

Resolves sources -> downloads PDFs -> extracts text -> chunks ->
per-doc intelligence extraction -> cross-doc landscape synthesis.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import structlog

from shared.external import ArxivClient
from shared.pdf import chunk_text, download_arxiv_pdf, extract_text

from hypo_claude.agents.extractor import LandscapeSynthesizer, PaperIntelligenceExtractor
from hypo_claude.llm.provider import LLMProvider

logger = structlog.get_logger(__name__)


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 0: Extract intelligence from all input papers."""

    arxiv_client = ArxivClient()

    try:
        # Resolve all paper sources
        arxiv_ids: list[str] = []
        if state.get("arxiv_id"):
            arxiv_ids.append(state["arxiv_id"])
        arxiv_ids.extend(state.get("arxiv_ids") or [])
        arxiv_ids = list(dict.fromkeys(arxiv_ids))  # dedupe preserving order

        if not arxiv_ids and not state.get("pdf_path"):
            raise ValueError("No input papers — provide arxiv_id, arxiv_ids, or pdf_path")

        if progress:
            await progress("intelligence", f"Processing {len(arxiv_ids)} paper(s)...", 0, len(arxiv_ids) + 1)

        # Download + extract text from all papers
        papers: list[tuple[str, str]] = []  # (text, paper_id)
        all_chunks: list[str] = []

        for i, aid in enumerate(arxiv_ids):
            try:
                pdf_path = await download_arxiv_pdf(aid)
                text = await extract_text(pdf_path)
                chunks = chunk_text(text, chunk_size=1500, overlap=200)
                papers.append((text, aid))
                all_chunks.extend(chunks)
                if progress:
                    await progress("intelligence", f"Extracted {aid}", i + 1, len(arxiv_ids) + 1)
            except Exception as e:
                logger.error("layer0.pdf_failed", arxiv_id=aid, error=str(e))

        # Handle direct PDF path
        if state.get("pdf_path") and not papers:
            from pathlib import Path
            text = await extract_text(Path(state["pdf_path"]))
            chunks = chunk_text(text, chunk_size=1500, overlap=200)
            papers.append((text, "local_pdf"))
            all_chunks.extend(chunks)

        if not papers:
            raise ValueError("Could not extract text from any papers")

        # Per-doc intelligence extraction (parallel)
        extractor = PaperIntelligenceExtractor(llm)
        intelligences = await extractor.extract_batch(papers, max_concurrent=3)

        if progress:
            await progress("intelligence", "Synthesizing research landscape...", len(arxiv_ids), len(arxiv_ids) + 1)

        # Cross-doc synthesis
        synthesizer = LandscapeSynthesizer(llm)
        landscape = await synthesizer.synthesize(intelligences)

        if progress:
            await progress("intelligence", "Intelligence extraction complete", len(arxiv_ids) + 1, len(arxiv_ids) + 1)

        return {
            "paper_intelligences": intelligences,
            "research_landscape": landscape,
            "text_chunks": all_chunks,
        }
    finally:
        await arxiv_client.close()
