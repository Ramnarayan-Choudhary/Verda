from __future__ import annotations

from statistics import mean, pvariance
from typing import Any

from hypo_gpt.layer4_panel.conservative_judge import judge_conservative
from hypo_gpt.layer4_panel.generalist_judge import judge_generalist
from hypo_gpt.layer4_panel.panel_schema import compute_panel_composite
from hypo_gpt.layer4_panel.practitioner_judge import judge_practitioner
from hypo_gpt.models import HypothesisV2, PanelVerdict


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def evaluate_panel(
    hypothesis: HypothesisV2,
    *,
    risk_appetite: str = "balanced",
    tribunal_bundle: dict[str, Any] | None = None,
) -> PanelVerdict:
    conservative = judge_conservative(hypothesis, tribunal_bundle=tribunal_bundle)
    generalist = judge_generalist(hypothesis, tribunal_bundle=tribunal_bundle)
    practitioner = judge_practitioner(hypothesis, tribunal_bundle=tribunal_bundle)
    scores = [conservative, generalist, practitioner]

    novelty_vals = [score.novelty for score in scores]
    feasibility_vals = [score.feasibility for score in scores]
    coherence_vals = [score.mechanism_coherence for score in scores]
    executability_vals = [score.executability for score in scores]
    importance_vals = [score.strategic_importance for score in scores]

    verdict = PanelVerdict(
        hypo_id=hypothesis.hypo_id,
        scores=scores,
        novelty_mean=_clip01(mean(novelty_vals)),
        novelty_var=round(pvariance(novelty_vals), 6),
        feasibility_mean=_clip01(mean(feasibility_vals)),
        feasibility_var=round(pvariance(feasibility_vals), 6),
        coherence_mean=_clip01(mean(coherence_vals)),
        coherence_var=round(pvariance(coherence_vals), 6),
        executability_mean=_clip01(mean(executability_vals)),
        executability_var=round(pvariance(executability_vals), 6),
        importance_mean=_clip01(mean(importance_vals)),
        importance_var=round(pvariance(importance_vals), 6),
        controversy_score=round(
            mean(
                [
                    pvariance(novelty_vals),
                    pvariance(feasibility_vals),
                    pvariance(coherence_vals),
                    pvariance(executability_vals),
                    pvariance(importance_vals),
                ]
            ),
            6,
        ),
        panel_composite=0.0,
    )
    verdict.panel_composite = compute_panel_composite(verdict, risk_appetite)
    return verdict
