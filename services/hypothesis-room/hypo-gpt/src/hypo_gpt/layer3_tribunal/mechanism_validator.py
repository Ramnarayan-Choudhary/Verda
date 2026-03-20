from __future__ import annotations

import re

from hypo_gpt.models import HypothesisV2


def validate_mechanism(hypothesis: HypothesisV2) -> dict:
    gaps = []
    contradictions = []

    if len(hypothesis.causal_chain.intermediate.split()) < 15:
        gaps.append("intermediate mechanism too shallow")
    if not hypothesis.causal_chain.conditions:
        gaps.append("missing boundary conditions")
    if re.search(r"\d", hypothesis.falsification_criterion) is None:
        gaps.append("falsification criterion lacks numeric threshold")

    conditions = " ".join(hypothesis.causal_chain.conditions).lower()
    breaks = " ".join(hypothesis.causal_chain.breaks_when).lower()
    if "always" in conditions and "always" in breaks:
        contradictions.append("conditions and breaks_when conflict")

    coherence = max(0.0, 1.0 - (0.18 * len(gaps)) - (0.25 * len(contradictions)))
    return {
        "coherence_score": round(coherence, 4),
        "gaps": gaps,
        "contradictions": contradictions,
        "is_logically_valid": coherence >= 0.55 and not contradictions,
    }
