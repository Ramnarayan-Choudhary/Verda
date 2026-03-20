from __future__ import annotations

import re
from statistics import mean, pvariance

from hypo_gpt.models import DimensionScores, HypothesisV2, JudgeScore, PanelVerdict, StructuredHypothesis


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def _clip10(value: float) -> float:
    return max(0.0, min(10.0, round(value, 2)))


def _has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _base_dimensions(hypothesis: HypothesisV2) -> tuple[float, float, float, float, float]:
    novelty = 0.52 + (0.18 if hypothesis.strategy in {"cross_domain", "constraint_relax", "method_recomb"} else 0.08)
    feasibility = 0.62 + (0.08 if "public" in hypothesis.experiment.required_data.lower() else -0.12)
    mechanism = 0.55 + (0.18 if len(hypothesis.causal_chain.intermediate.split()) >= 18 else 0.05)
    executability = 0.58 + (0.12 if _has_number(hypothesis.falsification_criterion) else -0.08)
    importance = 0.54 + (0.12 if "deployment" in hypothesis.problem_being_solved.lower() else 0.05)
    return (_clip01(novelty), _clip01(feasibility), _clip01(mechanism), _clip01(executability), _clip01(importance))


class PanelJudge:
    """3-judge dimensional panel with variance aggregation."""

    def evaluate_panel(self, hypothesis: HypothesisV2, risk_appetite: str = "balanced") -> PanelVerdict:
        novelty, feasibility, mechanism, executability, importance = _base_dimensions(hypothesis)

        conservative = JudgeScore(
            judge_id="conservative",
            novelty=_clip01(novelty - 0.08),
            feasibility=_clip01(feasibility + 0.10),
            mechanism_coherence=_clip01(mechanism + 0.05),
            executability=_clip01(executability + 0.07),
            strategic_importance=_clip01(importance - 0.02),
            reasoning={
                "novelty": "Discounted for risk-sensitive posture.",
                "feasibility": "Prioritizes practical reproducibility.",
            },
        )

        generalist = JudgeScore(
            judge_id="generalist",
            novelty=_clip01(novelty + 0.05),
            feasibility=_clip01(feasibility),
            mechanism_coherence=_clip01(mechanism),
            executability=_clip01(executability),
            strategic_importance=_clip01(importance + 0.08),
            reasoning={
                "novelty": "Rewards conceptual breadth.",
                "importance": "Values field-level relevance.",
            },
        )

        practitioner = JudgeScore(
            judge_id="practitioner",
            novelty=_clip01(novelty - 0.02),
            feasibility=_clip01(feasibility + 0.06),
            mechanism_coherence=_clip01(mechanism - 0.01),
            executability=_clip01(executability + 0.09),
            strategic_importance=_clip01(importance + 0.03),
            reasoning={
                "executability": "Emphasizes implementation realism.",
                "feasibility": "Prefers bounded compute/data requirements.",
            },
        )

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
        verdict.panel_composite = self.compute_panel_composite(verdict, risk_appetite=risk_appetite)
        return verdict

    @staticmethod
    def compute_panel_composite(verdict: PanelVerdict, risk_appetite: str) -> float:
        weights = {
            "conservative": dict(n=0.20, f=0.35, m=0.25, e=0.20, i=0.00),
            "balanced": dict(n=0.25, f=0.25, m=0.25, e=0.15, i=0.10),
            "moonshot": dict(n=0.40, f=0.10, m=0.20, e=0.10, i=0.20),
        }
        chosen = weights.get(risk_appetite, weights["balanced"])
        score = (
            (chosen["n"] * verdict.novelty_mean)
            + (chosen["f"] * verdict.feasibility_mean)
            + (chosen["m"] * verdict.coherence_mean)
            + (chosen["e"] * verdict.executability_mean)
            + (chosen["i"] * verdict.importance_mean)
        )
        return _clip01(score)

    def score(self, hypothesis: StructuredHypothesis) -> DimensionScores:
        v2 = HypothesisV2.from_structured(hypothesis)
        verdict = self.evaluate_panel(v2)
        return DimensionScores(
            mechanistic_quality=_clip10(verdict.coherence_mean * 10),
            novelty=_clip10(verdict.novelty_mean * 10),
            testability=_clip10(verdict.executability_mean * 10),
            scientific_impact=_clip10(verdict.importance_mean * 10),
            feasibility=_clip10(verdict.feasibility_mean * 10),
            specificity=_clip10((0.6 * verdict.executability_mean + 0.4 * verdict.coherence_mean) * 10),
            creativity=_clip10((0.7 * verdict.novelty_mean + 0.3 * verdict.importance_mean) * 10),
        )

    @staticmethod
    def composite(scores: DimensionScores) -> float:
        return round(
            scores.mechanistic_quality * 0.25
            + scores.novelty * 0.20
            + scores.testability * 0.20
            + scores.scientific_impact * 0.15
            + scores.feasibility * 0.10
            + scores.specificity * 0.05
            + scores.creativity * 0.05,
            3,
        )
