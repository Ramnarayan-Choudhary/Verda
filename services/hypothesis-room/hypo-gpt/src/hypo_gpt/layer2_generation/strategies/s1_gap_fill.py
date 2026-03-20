from __future__ import annotations

import re

from hypo_gpt.models import GapAnalysis


def _topic(statement: str) -> str:
    text = re.sub(r"^mechanistic attribution gap for\s+'?", "", statement, flags=re.IGNORECASE).strip(" .'\"")
    return text[:72] if text else "deployment robustness"


def generate_s1(gap: GapAnalysis, *, round_index: int = 0) -> dict[str, str]:
    topic = _topic(gap.statement)
    return {
        "title_seed": f"Mediator Isolation for {topic}",
        "condition": f"When causal attribution for {topic} remains unresolved under deployment-like shifts",
        "core_claim": (
            f"Introduce a mechanism-targeted intervention that directly addresses {gap.gap_id} while keeping compute and data budget fixed."
        ),
        "mechanism_bias": (
            "Identify and instrument causal mediators linked to the gap, then isolate them via targeted ablations."
        ),
        "outcome": "Primary metric improves with reduced robustness variance under stress splits.",
        "falsification": "Disproved if shifted-split metric is < 1.03x baseline under strict equal-compute controls.",
        "design": "Controlled intervention + mediator probe + factorized equal-compute ablation ladder across 3 random seeds.",
        "success_threshold": ">=2% relative gain with <=1% robustness variance increase",
    }
