"""Layer 0 agents — Paper intelligence extraction and landscape synthesis."""

from __future__ import annotations

import asyncio
import json

import structlog

from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.llm.prompts.intelligence import (
    landscape_synthesis_prompt,
    paper_intelligence_prompt,
)
from hypo_claude.models import PaperIntelligence, ResearchLandscape

logger = structlog.get_logger(__name__)


class PaperIntelligenceExtractor:
    """Extracts deep structured intelligence from a single paper."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def extract(self, paper_text: str, paper_id: str = "", domain: str = "") -> PaperIntelligence:
        system, user = paper_intelligence_prompt(paper_text, domain=domain)
        result = await self._llm.generate_json(
            system, user,
            model_class=PaperIntelligence,
            temperature=0.2,
            role=AgentRole.PAPER_EXTRACTOR,
        )
        if paper_id:
            result.paper_id = paper_id  # type: ignore[union-attr]
        # Fallback: extract title from paper text if LLM returned garbage
        _garbage_titles = {"", "PaperIntelligence", "paper_intelligence", "Unknown", "N/A", "null", "None"}
        if not result.title or result.title.strip() in _garbage_titles:  # type: ignore[union-attr]
            first_lines = paper_text.strip().split("\n")
            for line in first_lines[:5]:
                line = line.strip()
                if len(line) > 10 and not line.startswith(("arXiv", "http", "doi", "Abstract")):
                    result.title = line[:200]  # type: ignore[union-attr]
                    break
            if not result.title:  # type: ignore[union-attr]
                result.title = f"Paper {paper_id or 'unknown'}"  # type: ignore[union-attr]
        logger.info("extractor.paper_done", paper_id=paper_id, title=result.title[:60])  # type: ignore[union-attr]
        return result  # type: ignore[return-value]

    async def extract_batch(
        self, papers: list[tuple[str, str]], max_concurrent: int = 3
    ) -> list[PaperIntelligence]:
        """Extract intelligence from multiple papers concurrently.

        Args:
            papers: List of (paper_text, paper_id) tuples
            max_concurrent: Max parallel extractions
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded(text: str, pid: str) -> PaperIntelligence:
            async with semaphore:
                return await self.extract(text, pid)

        tasks = [_bounded(text, pid) for text, pid in papers]
        return await asyncio.gather(*tasks)


class LandscapeSynthesizer:
    """Synthesizes multiple paper intelligences into a unified research landscape."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def synthesize(self, intelligences: list[PaperIntelligence], domain: str = "") -> ResearchLandscape:
        intel_data = [i.model_dump() for i in intelligences]
        intel_json = json.dumps(intel_data, indent=1)
        # Infer domain from first paper if not provided
        if not domain and intelligences:
            domain = intelligences[0].domain or ""
        system, user = landscape_synthesis_prompt(intel_json, len(intelligences), domain=domain)

        result = await self._llm.generate_json(
            system, user,
            model_class=ResearchLandscape,
            temperature=0.3,
            role=AgentRole.LANDSCAPE_SYNTHESIZER,
        )
        logger.info(
            "synthesizer.landscape_done",
            intent=result.research_intent[:60],  # type: ignore[union-attr]
            n_assumptions=len(result.shared_assumptions),  # type: ignore[union-attr]
            n_contradictions=len(result.contested_claims),  # type: ignore[union-attr]
        )
        return result  # type: ignore[return-value]
