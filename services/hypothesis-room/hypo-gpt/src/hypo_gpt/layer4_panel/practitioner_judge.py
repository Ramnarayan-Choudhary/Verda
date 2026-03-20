from __future__ import annotations

from typing import Any

from hypo_gpt.models import HypothesisV2, JudgeScore


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def judge_practitioner(hypothesis: HypothesisV2, tribunal_bundle: dict[str, Any] | None = None) -> JudgeScore:
    tribunal_bundle = tribunal_bundle or {}
    resource_verdict = (tribunal_bundle.get("resource") or {}).get("resource_verdict", "accept")
    exec_verdict = (tribunal_bundle.get("executability") or {}).get("exec_verdict", "accept")
    method_verdict = (tribunal_bundle.get("methodology") or {}).get("method_verdict", "accept")

    novelty = _clip01(hypothesis.novelty - 0.03)
    feasibility = _clip01(hypothesis.feasibility + (0.09 if resource_verdict == "accept" else -0.08))
    mechanism = _clip01(hypothesis.mechanism_coherence + (0.03 if method_verdict == "accept" else -0.06))
    executability = _clip01(hypothesis.executability + (0.10 if exec_verdict == "accept" else -0.12))
    importance = _clip01(hypothesis.composite_score + 0.04)

    return JudgeScore(
        judge_id="practitioner",
        novelty=novelty,
        feasibility=feasibility,
        mechanism_coherence=mechanism,
        executability=executability,
        strategic_importance=importance,
        reasoning={
            "stance": "execution-first",
            "principle": "Prioritize implementation reliability and data/compute realism over novelty premium.",
        },
    )
