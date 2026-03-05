"""Layer 1 agents — Gap analysis and research space mapping."""

from __future__ import annotations

import json

import structlog

from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.llm.prompts.cartography import gap_taxonomy_prompt
from hypo_claude.models import PaperIntelligence, ResearchLandscape, ResearchSpaceMap

logger = structlog.get_logger(__name__)


class GapAnalyst:
    """Analyzes research landscape to identify 4-type gap taxonomy."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def analyze(
        self,
        landscape: ResearchLandscape,
        intelligences: list[PaperIntelligence],
        related_papers_json: str = "[]",
    ) -> ResearchSpaceMap:
        landscape_json = json.dumps(landscape.model_dump(), indent=1)
        paper_titles = [i.title for i in intelligences if i.title]

        system, user = gap_taxonomy_prompt(landscape_json, paper_titles, related_papers_json)

        result = await self._llm.generate_json(
            system, user,
            model_class=ResearchSpaceMap,
            temperature=0.3,
            role=AgentRole.GAP_ANALYST,
        )

        space_map: ResearchSpaceMap = result  # type: ignore[assignment]
        n_gaps = len(space_map.all_gaps)
        n_targets = len(space_map.high_value_targets)
        logger.info("cartographer.gaps_found", total_gaps=n_gaps, high_value_targets=n_targets)
        return space_map
