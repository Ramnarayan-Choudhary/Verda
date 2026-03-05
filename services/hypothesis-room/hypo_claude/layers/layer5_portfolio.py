"""Layer 5 — Strategic Portfolio Construction.

Independence analysis, slot assignment, sequencing.
"""

from __future__ import annotations

from typing import Any, Callable

import structlog

from hypo_claude.agents.portfolio import PortfolioConstructor
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import (
    JudgeScore,
    PipelineConfig,
    StructuredHypothesis,
    TribunalVerdict,
)

logger = structlog.get_logger(__name__)


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 5: Construct a balanced research portfolio."""

    ranked: list[StructuredHypothesis] = state.get("ranked_hypotheses", [])
    panel_scores: dict[str, list[JudgeScore]] = state.get("panel_scores", {})
    verdicts: dict[str, TribunalVerdict] = state.get("tribunal_verdicts", {})
    config: PipelineConfig = state.get("config", PipelineConfig())

    if not ranked:
        logger.warning("layer5.no_hypotheses")
        from hypo_claude.models import ResearchPortfolio
        return {"research_portfolio": ResearchPortfolio()}

    if progress:
        await progress("portfolio", "Constructing research portfolio...", 0, 2)

    constructor = PortfolioConstructor(llm)
    portfolio = await constructor.construct(ranked, panel_scores, verdicts, config)

    if progress:
        n = len(portfolio.hypotheses)
        slots = {
            "safe": len(portfolio.safe_hypotheses),
            "medium": len(portfolio.medium_hypotheses),
            "moonshot": len(portfolio.moonshot_hypotheses),
        }
        await progress("portfolio", f"Portfolio: {n} hypotheses — {slots}", 2, 2)

    return {"research_portfolio": portfolio}
