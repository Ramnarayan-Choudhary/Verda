from __future__ import annotations

import re

from hypo_gpt.models import GapAnalysis


def _topic(statement: str) -> str:
    text = re.sub(r"^mechanistic attribution gap for\s+'?", "", statement, flags=re.IGNORECASE).strip(" .'\"")
    return text[:72] if text else "anomalous regime behavior"


def generate_s6(gap: GapAnalysis, *, round_index: int = 0) -> dict[str, str]:
    topic = _topic(gap.statement)
    return {
        "title_seed": f"Abductive Mechanism for {topic}",
        "condition": f"When anomaly around {topic.lower()} cannot be explained by prevailing mechanism",
        "core_claim": (
            f"Introduce a parsimonious latent mediator explaining anomaly tied to {gap.gap_id}, then test causal necessity."
        ),
        "mechanism_bias": "Propose minimal additional mediator and verify that removing it collapses anomaly resolution.",
        "outcome": "Anomalous behavior is explained and controlled without harming baseline performance.",
        "falsification": "Disproved if anomaly persists above baseline by >0.8% after mediator-targeted intervention.",
        "design": "Anomaly-focused stress suite with mediator on/off interventions and counterfactual checks.",
        "success_threshold": ">=20% anomaly reduction and non-negative base metric change",
    }
