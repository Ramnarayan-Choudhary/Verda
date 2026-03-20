"""Layer 0 — Multi-Document Intelligence.

Resolves sources -> downloads PDFs -> extracts text -> chunks ->
per-doc intelligence extraction -> cross-doc landscape synthesis.
Optionally runs Deep Research Mode for iterative literature search.
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
    config = state.get("config")

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
        domain = getattr(config, "domain", "") if config else ""
        extractor = PaperIntelligenceExtractor(llm)
        intelligences = await extractor.extract_batch(papers, max_concurrent=3)

        if progress:
            await progress("intelligence", "Synthesizing research landscape...", len(arxiv_ids), len(arxiv_ids) + 1)

        # Cross-doc synthesis
        synthesizer = LandscapeSynthesizer(llm)
        landscape = await synthesizer.synthesize(intelligences, domain=domain)

        # Deep Research Mode: iterative search-read-refine (SciSpace-inspired)
        enable_deep_research = getattr(config, "enable_deep_research", False) if config else False
        if enable_deep_research:
            from hypo_claude.agents.deep_research import DeepResearchAgent

            deep_rounds = getattr(config, "deep_research_rounds", 3) if config else 3
            max_papers_per_round = getattr(config, "max_papers_per_round", 10) if config else 10
            follow_citations = getattr(config, "follow_citations", True) if config else True

            if progress:
                await progress(
                    "intelligence",
                    f"Starting Deep Research Mode ({deep_rounds} rounds)...",
                    len(arxiv_ids), len(arxiv_ids) + 2,
                )

            deep_agent = DeepResearchAgent(
                llm=llm,
                extractor=extractor,
                synthesizer=synthesizer,
                progress_callback=None,  # Use layer-level progress instead
            )

            intelligences, landscape = await deep_agent.run(
                initial_intelligences=intelligences,
                initial_landscape=landscape,
                rounds=deep_rounds,
                max_papers_per_round=max_papers_per_round,
                follow_citations=follow_citations,
                domain=domain,
            )

            if progress:
                await progress(
                    "intelligence",
                    f"Deep Research complete: {len(intelligences)} papers analyzed",
                    len(arxiv_ids) + 1, len(arxiv_ids) + 2,
                )

        if progress:
            await progress("intelligence", "Intelligence extraction complete", len(arxiv_ids) + 1, len(arxiv_ids) + 1)

        return {
            "paper_intelligences": intelligences,
            "research_landscape": landscape,
            "text_chunks": all_chunks,
        }
    finally:
        await arxiv_client.close()
