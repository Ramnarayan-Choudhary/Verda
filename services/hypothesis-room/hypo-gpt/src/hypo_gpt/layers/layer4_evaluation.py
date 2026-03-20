from __future__ import annotations

import structlog

from hypo_gpt.agents.judges import PanelJudge
from hypo_gpt.layer4_panel.panel import evaluate_panel
from hypo_gpt.models import DimensionScores, PipelineState

logger = structlog.get_logger(__name__)


def _to_legacy_dimension_scores(verdict) -> DimensionScores:
    return DimensionScores(
        mechanistic_quality=round(verdict.coherence_mean * 10, 2),
        novelty=round(verdict.novelty_mean * 10, 2),
        testability=round(verdict.executability_mean * 10, 2),
        scientific_impact=round(verdict.importance_mean * 10, 2),
        feasibility=round(verdict.feasibility_mean * 10, 2),
        specificity=round(((0.6 * verdict.executability_mean) + (0.4 * verdict.coherence_mean)) * 10, 2),
        creativity=round(((0.7 * verdict.novelty_mean) + (0.3 * verdict.importance_mean)) * 10, 2),
    )


async def run(state: PipelineState) -> PipelineState:
    judge = PanelJudge()

    if state.refined_hypotheses_v2:
        scored = []
        panel_verdicts = {}
        for hypothesis in state.refined_hypotheses_v2:
            tribunal_bundle = state.tribunal_verdicts_v2.get(hypothesis.hypo_id)
            verdict = evaluate_panel(
                hypothesis,
                risk_appetite=state.config.risk_appetite,
                tribunal_bundle=tribunal_bundle,
            )
            panel_verdicts[hypothesis.hypo_id] = verdict
            structured = hypothesis.to_structured()
            dims = _to_legacy_dimension_scores(verdict)
            state.dimension_scores[structured.id] = dims
            scored.append((verdict.panel_composite, structured))

        scored.sort(key=lambda item: item[0], reverse=True)
        state.panel_verdicts = panel_verdicts
        state.ranked_hypotheses = [hypothesis for _, hypothesis in scored]

        logger.info("hypo_gpt.layer4.complete.v2", ranked=len(state.ranked_hypotheses))
        return state

    if not state.refined_hypotheses:
        state.errors.append("Layer4: no refined hypotheses")
        return state

    scored = []
    for hypothesis in state.refined_hypotheses:
        score = judge.score(hypothesis)
        state.dimension_scores[hypothesis.id] = score
        scored.append((judge.composite(score), hypothesis))

    scored.sort(key=lambda item: item[0], reverse=True)
    state.ranked_hypotheses = [hypothesis for _, hypothesis in scored]

    logger.info("hypo_gpt.layer4.complete", ranked=len(state.ranked_hypotheses))
    return state
