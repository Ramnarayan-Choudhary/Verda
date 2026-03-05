from __future__ import annotations

import re

from hypo_gpt.models import DimensionScores, StructuredHypothesis


def _clip(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 2)


def _has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _parse_compute_intensity(compute: str) -> float:
    lower = compute.lower()
    if "16x" in lower:
        return 0.9
    if "8x" in lower:
        return 0.7
    if "4x" in lower:
        return 0.45
    if "2x" in lower:
        return 0.3
    return 0.5


class PanelJudge:
    """Scores hypotheses using 3 perspectives and returns aggregated scores."""

    def score(self, hypothesis: StructuredHypothesis) -> DimensionScores:
        mechanism_words = len(hypothesis.mechanism.split())
        mechanism_quality = 5.6 + min(2.6, mechanism_words / 12.0)
        if "causal" in hypothesis.mechanism.lower():
            mechanism_quality += 0.6
        if "ablation" in hypothesis.falsification_criterion.lower():
            mechanism_quality += 0.3

        novelty = 5.8
        if hypothesis.generation_strategy in {"domain_bridge", "constraint_relaxer", "synthesis_catalyst"}:
            novelty += 1.6
        if hypothesis.generation_strategy in {"contradiction_resolver", "falsification_designer"}:
            novelty += 1.2
        novelty += min(1.0, len(hypothesis.novelty_claim.split()) / 24.0)

        testability = 5.4
        if _has_number(hypothesis.prediction):
            testability += 1.4
        if _has_number(hypothesis.minimum_viable_test.success_threshold):
            testability += 1.0
        if hypothesis.minimum_viable_test.dataset:
            testability += 0.7
        if "reject" in hypothesis.falsification_criterion.lower() or "fail" in hypothesis.falsification_criterion.lower():
            testability += 0.6

        impact = 5.7
        for token in ("robust", "deployment", "generaliz", "safety", "efficien"):
            if token in f"{hypothesis.intervention} {hypothesis.prediction}".lower():
                impact += 0.4

        compute_intensity = _parse_compute_intensity(hypothesis.minimum_viable_test.estimated_compute)
        feasibility = 8.2 - (compute_intensity * 2.0)
        if "weeks" in hypothesis.minimum_viable_test.estimated_timeline.lower():
            feasibility += 0.2

        specificity = 5.8
        if _has_number(hypothesis.prediction):
            specificity += 0.8
        if len(hypothesis.intervention.split()) >= 18:
            specificity += 0.8
        if len(hypothesis.minimum_viable_test.baseline.split()) >= 6:
            specificity += 0.6

        creativity = 5.4
        if hypothesis.generation_strategy in {"domain_bridge", "synthesis_catalyst"}:
            creativity += 2.2
        elif hypothesis.generation_strategy in {"constraint_relaxer", "assumption_challenger"}:
            creativity += 1.5
        creativity += min(0.8, len(hypothesis.title.split()) / 16.0)

        if hypothesis.generation_strategy == "falsification_designer":
            testability += 0.9
            specificity += 0.7
            novelty += 0.4
        elif hypothesis.generation_strategy == "domain_bridge":
            creativity += 0.9
            feasibility -= 0.6
            impact += 0.4
        elif hypothesis.generation_strategy == "constraint_relaxer":
            novelty += 0.7
            feasibility -= 0.4
        elif hypothesis.generation_strategy == "assumption_challenger":
            feasibility += 0.4
            testability += 0.3

        conservative = {
            "mechanistic_quality": mechanism_quality,
            "novelty": novelty - 0.5,
            "testability": testability + 0.2,
            "scientific_impact": impact - 0.2,
            "feasibility": feasibility + 0.3,
            "specificity": specificity + 0.2,
            "creativity": creativity - 0.6,
        }
        generalist = {
            "mechanistic_quality": mechanism_quality + 0.3,
            "novelty": novelty + 0.2,
            "testability": testability,
            "scientific_impact": impact + 0.4,
            "feasibility": feasibility - 0.2,
            "specificity": specificity,
            "creativity": creativity + 0.4,
        }
        practitioner = {
            "mechanistic_quality": mechanism_quality - 0.1,
            "novelty": novelty - 0.1,
            "testability": testability + 0.5,
            "scientific_impact": impact,
            "feasibility": feasibility + 0.1,
            "specificity": specificity + 0.3,
            "creativity": creativity,
        }

        def avg(key: str) -> float:
            return _clip((conservative[key] + generalist[key] + practitioner[key]) / 3)

        return DimensionScores(
            mechanistic_quality=avg("mechanistic_quality"),
            novelty=avg("novelty"),
            testability=avg("testability"),
            scientific_impact=avg("scientific_impact"),
            feasibility=avg("feasibility"),
            specificity=avg("specificity"),
            creativity=avg("creativity"),
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
