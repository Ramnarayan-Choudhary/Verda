from __future__ import annotations

import re

from hypo_gpt.models import GapAnalysis


def _topic(statement: str) -> str:
    text = re.sub(r"^assumption\s+'?", "", statement, flags=re.IGNORECASE).strip(" .'\"")
    return text[:72] if text else "current evaluation assumptions"


def generate_s3(gap: GapAnalysis, *, round_index: int = 0) -> dict[str, str]:
    topic = _topic(gap.statement)
    return {
        "title_seed": f"Assumption Stress Test for {topic}",
        "condition": f"If the core assumption '{topic}' fails under deployment shift",
        "core_claim": (
            f"Relax a hidden assumption tied to {gap.gap_id} and replace it with measurable, stress-tested boundary conditions."
        ),
        "mechanism_bias": "Expose assumption-sensitive pathways and test whether intervention still works once assumption is removed.",
        "outcome": "System maintains performance when assumption is violated in controlled stress environments.",
        "falsification": "Disproved if intervention is < 1.02x baseline when assumption-violation stressors are applied.",
        "design": "Assumption-on vs assumption-off protocol with equal-compute controls.",
        "success_threshold": ">=2% relative gain specifically in assumption-violated evaluation subsets",
    }
