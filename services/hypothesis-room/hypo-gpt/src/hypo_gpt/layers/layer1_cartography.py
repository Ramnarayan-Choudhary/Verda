from __future__ import annotations

import structlog

from hypo_gpt.agents.cartographer import GapAnalyst
from hypo_gpt.models import PipelineState

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    if state.research_landscape is None:
        state.errors.append("Layer1: missing research landscape")
        return state

    analyst = GapAnalyst()
    state.research_space_map = analyst.map(state.research_landscape)
    logger.info(
        "hypo_gpt.layer1.complete",
        knowledge=len(state.research_space_map.knowledge_gaps),
        method=len(state.research_space_map.method_gaps),
        assumption=len(state.research_space_map.assumption_gaps),
        theoretical=len(state.research_space_map.theoretical_gaps),
    )
    return state
