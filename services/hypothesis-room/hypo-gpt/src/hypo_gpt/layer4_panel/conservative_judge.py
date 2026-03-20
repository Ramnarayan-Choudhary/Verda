from __future__ import annotations

from typing import Any

from hypo_gpt.models import HypothesisV2, JudgeScore


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def judge_conservative(hypothesis: HypothesisV2, tribunal_bundle: dict[str, Any] | None = None) -> JudgeScore:
    tribunal_bundle = tribunal_bundle or {}
    mechanism_valid = bool((tribunal_bundle.get("mechanism") or {}).get("is_logically_valid", True))
    resource_ok = (tribunal_bundle.get("resource") or {}).get("resource_verdict", "accept") == "accept"
    exec_ok = (tribunal_bundle.get("executability") or {}).get("exec_verdict", "accept") == "accept"
    domain_ok = (tribunal_bundle.get("domain") or {}).get("domain_verdict", "accept") == "accept"

    novelty = _clip01(hypothesis.novelty - 0.10)
    feasibility = _clip01(hypothesis.feasibility + (0.10 if resource_ok else -0.08))
    mechanism = _clip01(hypothesis.mechanism_coherence + (0.08 if mechanism_valid and domain_ok else -0.12))
    executability = _clip01(hypothesis.executability + (0.08 if exec_ok else -0.10))
    importance = _clip01(hypothesis.composite_score - 0.03)

    return JudgeScore(
        judge_id="conservative",
        novelty=novelty,
        feasibility=feasibility,
        mechanism_coherence=mechanism,
        executability=executability,
        strategic_importance=importance,
        reasoning={
            "stance": "risk-sensitive",
            "principle": "Prefer hypotheses with strong mechanism validity and implementation confidence.",
        },
    )
