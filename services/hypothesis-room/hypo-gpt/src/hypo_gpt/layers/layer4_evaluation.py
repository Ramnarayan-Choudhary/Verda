from __future__ import annotations

import structlog

from hypo_gpt.agents.judges import PanelJudge
from hypo_gpt.models import PipelineState

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    if not state.refined_hypotheses:
        state.errors.append("Layer4: no refined hypotheses")
        return state

    judge = PanelJudge()
    scored = []
    for hyp in state.refined_hypotheses:
        score = judge.score(hyp)
        state.dimension_scores[hyp.id] = score
        scored.append((judge.composite(score), hyp))

    scored.sort(key=lambda item: item[0], reverse=True)
    state.ranked_hypotheses = [hyp for _, hyp in scored]

    logger.info("hypo_gpt.layer4.complete", ranked=len(state.ranked_hypotheses))
    return state
