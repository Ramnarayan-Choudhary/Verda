from __future__ import annotations

import re

from hypo_gpt.models import GapAnalysis


def _topic(statement: str) -> str:
    text = re.sub(r"^factorized ablation protocol to isolate claimed causal components", "causal component interactions", statement, flags=re.IGNORECASE)
    text = text.strip(" .'\"")
    return text[:72] if text else "mechanism interactions"


def generate_s4(gap: GapAnalysis, *, round_index: int = 0) -> dict[str, str]:
    topic = _topic(gap.statement)
    return {
        "title_seed": f"Method Recombination for {topic}",
        "condition": f"When isolated methods underperform on {topic.lower()}",
        "core_claim": (
            f"Recombine complementary mechanisms around {gap.gap_id} into one coherent intervention with explicit causal partitioning."
        ),
        "mechanism_bias": (
            "Fuse stabilization and representation components, then verify additive contribution via factorized ablations."
        ),
        "outcome": "Combined method outperforms each single component under equal compute and data constraints.",
        "falsification": "Disproved if recombined method is < best_single_component + 1.0% under equal-compute regime.",
        "design": "Component-wise ablation grid with matched compute, fixed training schedule, and repeated-seed confidence intervals.",
        "success_threshold": ">=1.5% over best single component with non-degraded robustness variance",
    }
