from __future__ import annotations

import structlog

from hypo_gpt.agents.portfolio import PortfolioConstructor
from hypo_gpt.layer5_portfolio.constructor import fill_portfolio
from hypo_gpt.models import PipelineState

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    constructor = PortfolioConstructor()

    if state.panel_verdicts and state.refined_hypotheses_v2:
        hypo_map = {hypothesis.hypo_id: hypothesis for hypothesis in state.refined_hypotheses_v2}
        target_min = max(3, min(5, state.config.top_k))
        state.final_portfolio_v2 = fill_portfolio(
            list(state.panel_verdicts.values()),
            hypo_map,
            state.memory_entries,
            ensure_minimum=target_min,
        )
        state.ranked_hypotheses = [hypothesis.to_structured() for hypothesis in state.refined_hypotheses_v2]

    state.final_portfolio = constructor.build(
        state.ranked_hypotheses,
        state.dimension_scores,
        state.tribunal_verdicts,
    )

    logger.info(
        "hypo_gpt.layer5.complete",
        size=len(state.final_portfolio.hypotheses if state.final_portfolio else []),
        size_v2=len(state.final_portfolio_v2),
    )
    return state
