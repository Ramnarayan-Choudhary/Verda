from __future__ import annotations

from pathlib import Path

import structlog

from hypo_gpt.agents.extractor import LandscapeSynthesizer, PaperIntelligenceExtractor
from hypo_gpt.models import InputDocument, PipelineState
from shared.external import ArxivClient
from shared.pdf import extract_text

logger = structlog.get_logger(__name__)


async def _load_documents(input_documents: list[InputDocument]) -> list[tuple[str, str, int | None]]:
    arxiv = ArxivClient()
    loaded: list[tuple[str, str, int | None]] = []
    try:
        for doc in input_documents:
            if doc.type == "text" and doc.text:
                loaded.append((doc.title or "Text document", doc.text, None))
                continue
            if doc.type == "pdf" and doc.pdf_path:
                text = await extract_text(Path(doc.pdf_path))
                loaded.append((doc.title or Path(doc.pdf_path).stem, text, None))
                continue
            if doc.type == "arxiv" and doc.arxiv_id:
                meta = await arxiv.fetch_metadata(doc.arxiv_id)
                pdf_path = await arxiv.download_pdf(doc.arxiv_id)
                text = await extract_text(pdf_path)
                loaded.append((meta.title or (doc.title or doc.arxiv_id), text, meta.year))
                continue
        return loaded
    finally:
        await arxiv.close()


async def run(state: PipelineState) -> PipelineState:
    extractor = PaperIntelligenceExtractor()
    synthesizer = LandscapeSynthesizer()

    docs = await _load_documents(state.input_documents)
    if not docs:
        state.errors.append("Layer0: no documents loaded")
        state.research_landscape = synthesizer.synthesize(state.research_intent, [])
        return state

    intelligences = [extractor.extract(title=title, text=text, year=year) for title, text, year in docs]
    state.paper_intelligences = intelligences
    state.research_landscape = synthesizer.synthesize(state.research_intent, intelligences)
    logger.info("hypo_gpt.layer0.complete", documents=len(intelligences))
    return state
