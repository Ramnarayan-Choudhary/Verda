from __future__ import annotations

import re

from hypo_gpt.models import GapAnalysis


def _topic(statement: str) -> str:
    text = re.sub(r"^transfer\s+", "", statement, flags=re.IGNORECASE).strip(" .'\"")
    return text[:72] if text else "target task"


def generate_s2(gap: GapAnalysis, *, round_index: int = 0) -> dict[str, str]:
    topic = _topic(gap.statement)
    return {
        "title_seed": f"Cross-Domain Mechanism Transfer for {topic}",
        "condition": f"Under regime where single-domain methods for {topic} plateau under shift",
        "core_claim": (
            f"Transfer a structurally analogous mechanism from adjacent domains to address {gap.gap_id} with strict compute parity."
        ),
        "mechanism_bias": (
            "Map invariant control principles across domains and encode them as optimization constraints with explicit mediator readouts."
        ),
        "outcome": "Cross-domain transfer improves robustness-adjusted performance and reduces out-of-domain degradation.",
        "falsification": "Disproved if transfer variant is < 1.03x baseline on shifted split or < 0.99x on in-domain split.",
        "design": "Construct transfer baseline, then run matched-compute cross-domain ablation matrix with repeated seeds.",
        "success_threshold": ">=3% gain on shifted split and >=0% change on in-domain split",
    }
