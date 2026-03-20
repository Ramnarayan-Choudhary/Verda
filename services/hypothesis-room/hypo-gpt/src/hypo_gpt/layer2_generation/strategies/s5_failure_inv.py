from __future__ import annotations

import re

from hypo_gpt.models import GapAnalysis


def _topic(statement: str) -> str:
    text = re.sub(r"^conflicting evidence around\s+'?", "", statement, flags=re.IGNORECASE).strip(" .'\"")
    return text[:72] if text else "recurring failure patterns"


def generate_s5(gap: GapAnalysis, *, round_index: int = 0) -> dict[str, str]:
    topic = _topic(gap.statement)
    return {
        "title_seed": f"Failure-Signal Inversion for {topic}",
        "condition": f"When known failure mode linked to {topic.lower()} appears repeatedly",
        "core_claim": (
            f"Treat historical failure pattern as supervision signal and invert it into a causal intervention for {gap.gap_id}."
        ),
        "mechanism_bias": "Convert failure-trigger features into active control signals with explicit guardrail ablations.",
        "outcome": "Failure frequency decreases while core accuracy remains stable under shift.",
        "falsification": "Disproved if failure rate is > baseline by 0.5% under identical stress and compute settings.",
        "design": "Failure-conditioned training vs baseline with failure taxonomy instrumentation and counterfactual checks.",
        "success_threshold": ">=15% reduction in failure events with <=1% drop in core metric",
    }
