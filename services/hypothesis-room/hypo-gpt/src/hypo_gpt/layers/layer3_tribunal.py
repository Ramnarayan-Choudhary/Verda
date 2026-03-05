from __future__ import annotations

import structlog

from hypo_gpt.agents.tribunal import TribunalAgent
from hypo_gpt.models import PipelineState

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    if not state.hypothesis_pool:
        state.errors.append("Layer3: empty hypothesis pool")
        return state

    tribunal = TribunalAgent()
    working = list(state.hypothesis_pool)

    for cycle in range(state.config.tribunal_cycles):
        next_round = []
        for hyp in working:
            verdict = tribunal.review(hyp)
            state.tribunal_verdicts[hyp.id] = verdict
            next_round.append(tribunal.evolve(hyp, verdict))
        working = next_round
        state.refinement_cycle = cycle + 1

    state.refined_hypotheses = working
    logger.info("hypo_gpt.layer3.complete", hypotheses=len(working), cycles=state.refinement_cycle)
    return state
