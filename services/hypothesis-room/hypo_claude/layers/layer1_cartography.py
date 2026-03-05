"""Layer 1 — Research Space Cartography.

External grounding (S2, arXiv, PwC, web search) + 4-type gap analysis.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import structlog

from shared.external import (
    ArxivClient,
    PapersWithCodeClient,
    SemanticScholarClient,
    WebSearchClient,
)

from hypo_claude.agents.cartographer import GapAnalyst
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import PaperIntelligence, ResearchLandscape

logger = structlog.get_logger(__name__)


async def _gather_related(
    landscape: ResearchLandscape,
    intelligences: list[PaperIntelligence],
    arxiv_ids: list[str],
) -> list[dict]:
    """Fetch related papers from external APIs for grounding."""
    s2 = SemanticScholarClient()
    arxiv = ArxivClient()
    pwc = PapersWithCodeClient()

    try:
        all_related: list[dict] = []

        # Gather from S2: related papers for each input
        s2_tasks = []
        for aid in arxiv_ids[:3]:
            s2_tasks.append(s2.fetch_related(aid, limit=10))

        # Keyword search from landscape
        search_query = landscape.research_intent or landscape.dominant_paradigm
        if search_query:
            s2_tasks.append(s2.keyword_search(search_query, limit=10))

        s2_results = await asyncio.gather(*s2_tasks, return_exceptions=True)
        for result in s2_results:
            if isinstance(result, list):
                for paper in result:
                    all_related.append(paper.model_dump() if hasattr(paper, "model_dump") else {"title": str(paper)})

        # ArXiv search
        if search_query:
            try:
                arxiv_results = await arxiv.search(search_query, max_results=5)
                for paper in arxiv_results:
                    all_related.append(paper.model_dump() if hasattr(paper, "model_dump") else {"title": str(paper)})
            except Exception:
                pass

        return all_related[:50]  # Cap at 50 related papers
    finally:
        await asyncio.gather(s2.close(), arxiv.close(), return_exceptions=True)


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 1: Map the research space and identify gaps."""

    intelligences = state.get("paper_intelligences", [])
    landscape = state.get("research_landscape")

    if not landscape:
        raise ValueError("Layer 1 requires research_landscape from Layer 0")

    arxiv_ids = []
    if state.get("arxiv_id"):
        arxiv_ids.append(state["arxiv_id"])
    arxiv_ids.extend(state.get("arxiv_ids") or [])
    arxiv_ids = list(dict.fromkeys(arxiv_ids))

    if progress:
        await progress("cartography", "Gathering related literature...", 0, 3)

    # External grounding
    related_papers = await _gather_related(landscape, intelligences, arxiv_ids)

    if progress:
        await progress("cartography", f"Found {len(related_papers)} related papers", 1, 3)

    # Gap analysis
    analyst = GapAnalyst(llm)
    related_json = json.dumps(related_papers[:30], indent=1, default=str)
    space_map = await analyst.analyze(landscape, intelligences, related_json)

    if progress:
        await progress("cartography", f"Identified {len(space_map.all_gaps)} gaps", 2, 3)

    if progress:
        await progress("cartography", "Cartography complete", 3, 3)

    return {
        "research_space_map": space_map,
        "related_papers": related_papers,
    }
