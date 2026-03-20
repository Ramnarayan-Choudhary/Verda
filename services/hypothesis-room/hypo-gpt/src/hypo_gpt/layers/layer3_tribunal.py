from __future__ import annotations

import structlog

from hypo_gpt.agents.tribunal import TribunalAgent
from hypo_gpt.models import PipelineState

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    tribunal = TribunalAgent()

    if state.hypothesis_pool_v2:
        refined_v2 = []
        verdict_map: dict[str, dict] = {}

        for hypothesis in state.hypothesis_pool_v2:
            revised, verdict_bundle = await tribunal.review_hypothesis_v2(
                hypothesis,
                max_reentry_attempts=2,
            )
            verdict_map[hypothesis.hypo_id] = verdict_bundle
            if revised is not None:
                refined_v2.append(revised)

        state.tribunal_verdicts_v2 = verdict_map
        state.refined_hypotheses_v2 = refined_v2
        state.refined_hypotheses = [hypothesis.to_structured() for hypothesis in refined_v2]

        legacy_verdicts = {}
        for hypothesis in state.refined_hypotheses:
            verdict = tribunal.to_legacy_verdict(hypothesis)
            legacy_verdicts[hypothesis.id] = verdict
        state.tribunal_verdicts = legacy_verdicts

        state.refinement_cycle = 3
        logger.info(
            "hypo_gpt.layer3.complete.v2",
            input_count=len(state.hypothesis_pool_v2),
            refined_count=len(state.refined_hypotheses_v2),
        )
        return state

    if not state.hypothesis_pool:
        state.errors.append("Layer3: empty hypothesis pool")
        return state

    working = list(state.hypothesis_pool)
    for cycle in range(state.config.tribunal_cycles):
        next_round = []
        for hypothesis in working:
            verdict = tribunal.to_legacy_verdict(hypothesis)
            state.tribunal_verdicts[hypothesis.id] = verdict
            next_round.append(tribunal.evolve(hypothesis, verdict))
        working = next_round
        state.refinement_cycle = cycle + 1

    state.refined_hypotheses = working
    logger.info("hypo_gpt.layer3.complete", hypotheses=len(working), cycles=state.refinement_cycle)
    return state
