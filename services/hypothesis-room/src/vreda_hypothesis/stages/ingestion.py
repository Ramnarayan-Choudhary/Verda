"""Stage 1 — Paper Ingestion & Extraction."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from vreda_hypothesis.external import ArxivClient
from vreda_hypothesis.knowledge import PaperKnowledgeGraph
from vreda_hypothesis.llm import AgentRole
from vreda_hypothesis.llm.prompts import paper_extraction_prompts
from vreda_hypothesis.llm.prompts.research_frame import research_frame_prompt
from vreda_hypothesis.models import PaperMetadata, PaperSummary, ResearchFrame, PipelineState, StageError
from vreda_hypothesis.runtime import PipelineRuntime

logger = structlog.get_logger(__name__)


async def run(state: PipelineState, runtime: PipelineRuntime) -> dict[str, Any]:
    """Fetch paper text, run structured extraction, initialize knowledge graph + vector store."""
    try:
        metadata, pdf_path = await _resolve_source(state, runtime.arxiv)
        text = await _extract_pdf_text(pdf_path)
        chunks = _chunk_text(text)
        logger.info(
            "stage.ingestion.text_stats",
            characters=len(text),
            words=len(text.split()),
            chunks=len(chunks),
            source=str(pdf_path),
        )

        system, user = paper_extraction_prompts(text, metadata)
        summary = await runtime.llm.generate_json(
            system, user, PaperSummary,
            temperature=0.2,
            role=AgentRole.PAPER_EXTRACTION,
        )
        summary.title = summary.title or metadata.title
        summary.domain = summary.domain or state.config.domain or "other"

        # Update metadata title with LLM-extracted title so downstream stages
        # (grounding, overgeneration) have the real paper title instead of
        # a temp file stem like "vreda_hyp_3f66f168..._trail".
        if summary.title and summary.title != metadata.title:
            logger.info(
                "stage.ingestion.title_updated",
                original=metadata.title[:80],
                extracted=summary.title[:80],
            )
            metadata.title = summary.title

        # Extract ResearchFrame — deep mechanistic decomposition (AI-Researcher pattern)
        rf_system, rf_user = research_frame_prompt(text, metadata)
        try:
            research_frame = await runtime.llm.generate_json(
                rf_system, rf_user, ResearchFrame,
                temperature=0.2,
                role=AgentRole.PAPER_EXTRACTION,
            )
            logger.info(
                "stage.ingestion.research_frame",
                operators=len(research_frame.core_operators),
                gains=len(research_frame.claimed_gains),
                untested_axes=len(research_frame.untested_axes),
            )
        except Exception as rf_exc:
            logger.warning("stage.ingestion.research_frame_failed", error=str(rf_exc))
            research_frame = None
            state.errors.append(StageError(stage="ingestion", message=f"ResearchFrame extraction failed: {rf_exc}"))

        graph = PaperKnowledgeGraph()
        graph.add_paper(metadata, summary=summary, source="primary")

        doc_id = metadata.arxiv_id or metadata.title or "paper"
        await runtime.vector_store.add_chunks(doc_id, chunks)

        updates = {
            "paper_metadata": metadata,
            "paper_summary": summary,
            "paper_text": text,
            "text_chunks": chunks,
            "research_frame": research_frame,
            "knowledge_graph": graph,
            "vector_store_client": runtime.vector_store,
        }
        logger.info("stage.ingestion.complete", doc_id=doc_id, chunks=len(chunks))
        return updates
    except Exception as exc:
        logger.exception("stage.ingestion.error", error=str(exc))
        state.errors.append(StageError(stage="ingestion", message=str(exc), recoverable=False))
        return {"errors": state.errors}


async def _resolve_source(state: PipelineState, arxiv_client: ArxivClient) -> tuple[PaperMetadata, Path]:
    """Determine source PDF path + metadata."""
    if state.arxiv_id:
        metadata = await arxiv_client.fetch_metadata(state.arxiv_id)
        pdf_path = await arxiv_client.download_pdf(state.arxiv_id)
        return metadata, pdf_path

    if state.pdf_path:
        path = Path(state.pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF path {path} not found")
        metadata = PaperMetadata(
            title=path.stem,
            arxiv_id=None,
            semantic_scholar_id=None,
            authors=[],
            abstract="",
        )
        return metadata, path

    raise ValueError("Either arxiv_id or pdf_path must be supplied.")


async def _extract_pdf_text(path: Path) -> str:
    """Extract unicode text from PDF asynchronously using PyMuPDF."""
    def _sync_extract() -> str:
        import fitz  # PyMuPDF

        def _word_count(text: str) -> int:
            return len([t for t in text.split() if t.strip()])

        def _extract_blocks(doc: fitz.Document) -> str:
            parts: list[str] = []
            for page in doc:
                blocks = page.get_text("blocks", sort=True)
                for block in blocks:
                    # PyMuPDF block tuple: (x0, y0, x1, y1, text, block_no, block_type)
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

            # Fallback for PDFs where default extraction loses most body text.
            fallback_text = _extract_blocks(doc).strip()
            if _word_count(fallback_text) > _word_count(primary_text):
                logger.warning(
                    "ingestion.pdf_text_fallback_used",
                    path=str(path),
                    primary_words=_word_count(primary_text),
                    fallback_words=_word_count(fallback_text),
                    pages=len(doc),
                )
                return fallback_text

            return primary_text

    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _sync_extract)
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Simple sliding-window chunker compatible with vector store ingestion."""
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
