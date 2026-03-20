from __future__ import annotations

from hypo_gpt.models import PanelVerdict


RISK_WEIGHTS = {
    "conservative": dict(n=0.20, f=0.35, m=0.25, e=0.20, i=0.00),
    "balanced": dict(n=0.25, f=0.25, m=0.25, e=0.15, i=0.10),
    "moonshot": dict(n=0.40, f=0.10, m=0.20, e=0.10, i=0.20),
}


def compute_panel_composite(verdict: PanelVerdict, risk_appetite: str) -> float:
    w = RISK_WEIGHTS.get(risk_appetite, RISK_WEIGHTS["balanced"])
    score = round(
        (w["n"] * verdict.novelty_mean)
        + (w["f"] * verdict.feasibility_mean)
        + (w["m"] * verdict.coherence_mean)
        + (w["e"] * verdict.executability_mean)
        + (w["i"] * verdict.importance_mean),
        4,
    )
    return max(0.0, min(1.0, score))
