from __future__ import annotations

import re

from hypo_gpt.models import GapAnalysis


def _topic(statement: str) -> str:
    text = re.sub(r"^unresolved theoretical bottleneck:\s*", "", statement, flags=re.IGNORECASE).strip(" .'\"")
    return text[:72] if text else "theoretical bottleneck"


def generate_s7(gap: GapAnalysis, *, round_index: int = 0) -> dict[str, str]:
    topic = _topic(gap.statement)
    return {
        "title_seed": f"Constraint Relaxation for {topic}",
        "condition": f"When performance ceiling persists around {topic.lower()} due to over-constrained design choices",
        "core_claim": (
            f"Relax one structural constraint around {gap.gap_id} while preserving safety/validity checks through controlled bounds."
        ),
        "mechanism_bias": "Identify which constraint drives ceiling, relax it incrementally, and track mediator behavior shift.",
        "outcome": "Ceiling is broken with measurable gain and bounded risk under stress evaluation.",
        "falsification": "Disproved if relaxed variant is < 1.02x baseline or increases risk metric by >1%.",
        "design": "Constraint sweep with fixed compute/data protocol, risk-metric gating, and rollback criteria.",
        "success_threshold": ">=2% gain with <=1% increase on primary risk indicator",
    }
