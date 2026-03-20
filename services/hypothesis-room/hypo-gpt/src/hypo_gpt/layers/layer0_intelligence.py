from __future__ import annotations

from pathlib import Path

import structlog

from hypo_gpt.agents.external_grounding import ExternalGrounder
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
            try:
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
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "hypo_gpt.layer0.document_load_failed",
                    doc_type=doc.type,
                    arxiv_id=doc.arxiv_id,
                    pdf_path=doc.pdf_path,
                    title=doc.title,
                    error=str(exc),
                )
        return loaded
    finally:
        await arxiv.close()


async def run(state: PipelineState) -> PipelineState:
    extractor = PaperIntelligenceExtractor()
    synthesizer = LandscapeSynthesizer()
    grounder = ExternalGrounder()

    try:
        docs = await _load_documents(state.input_documents)
        if not docs:
            state.errors.append("Layer0: no documents loaded")
            state.research_landscape = synthesizer.synthesize(state.research_intent, [])
            return state

        external_docs: list[tuple[str, str, int | None]] = []
        if state.config.enable_external_search:
            domain_hint = state.config.domain_hint or "ml"
            arxiv_ids = [doc.arxiv_id for doc in state.input_documents if doc.arxiv_id]
            try:
                external_docs = await grounder.gather_documents(
                    primary_title=docs[0][0],
                    research_intent=state.research_intent,
                    domain=domain_hint,
                    arxiv_id=arxiv_ids[0] if arxiv_ids else None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("hypo_gpt.layer0.external_grounding_failed", error=str(exc))

        combined_docs = docs + external_docs
        intelligences = [extractor.extract(title=title, text=text, year=year) for title, text, year in combined_docs]
        state.paper_intelligences = intelligences
        state.research_landscape = synthesizer.synthesize(state.research_intent, intelligences)
        if state.config.domain_hint:
            state.research_landscape.intent_domain = state.config.domain_hint
        logger.info(
            "hypo_gpt.layer0.complete",
            documents=len(intelligences),
            primary_documents=len(docs),
            external_documents=len(external_docs),
            intent_domain=state.research_landscape.intent_domain,
        )
        return state
    finally:
        await grounder.close()
