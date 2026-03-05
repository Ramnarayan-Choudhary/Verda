from __future__ import annotations

import structlog

from hypo_gpt.agents.portfolio import PortfolioConstructor
from hypo_gpt.models import PipelineState

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    constructor = PortfolioConstructor()
    state.final_portfolio = constructor.build(
        state.ranked_hypotheses,
        state.dimension_scores,
        state.tribunal_verdicts,
    )
    logger.info("hypo_gpt.layer5.complete", size=len(state.final_portfolio.hypotheses if state.final_portfolio else []))
    return state
