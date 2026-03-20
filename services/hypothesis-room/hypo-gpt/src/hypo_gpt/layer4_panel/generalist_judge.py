from __future__ import annotations

from typing import Any

from hypo_gpt.models import HypothesisV2, JudgeScore


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def judge_generalist(hypothesis: HypothesisV2, tribunal_bundle: dict[str, Any] | None = None) -> JudgeScore:
    tribunal_bundle = tribunal_bundle or {}
    domain_verdict = (tribunal_bundle.get("domain") or {}).get("domain_verdict", "accept")
    method_verdict = (tribunal_bundle.get("methodology") or {}).get("method_verdict", "accept")
    mechanism_score = float((tribunal_bundle.get("mechanism") or {}).get("coherence_score", hypothesis.mechanism_coherence))

    novelty = _clip01(hypothesis.novelty + 0.06)
    feasibility = _clip01(hypothesis.feasibility + (0.03 if method_verdict == "accept" else -0.04))
    mechanism = _clip01((0.6 * hypothesis.mechanism_coherence) + (0.4 * mechanism_score))
    executability = _clip01(hypothesis.executability + (0.02 if domain_verdict == "accept" else -0.06))
    importance = _clip01(hypothesis.composite_score + 0.08)

    return JudgeScore(
        judge_id="generalist",
        novelty=novelty,
        feasibility=feasibility,
        mechanism_coherence=mechanism,
        executability=executability,
        strategic_importance=importance,
        reasoning={
            "stance": "balanced",
            "principle": "Reward broad scientific relevance while keeping methodological sanity checks.",
        },
    )
