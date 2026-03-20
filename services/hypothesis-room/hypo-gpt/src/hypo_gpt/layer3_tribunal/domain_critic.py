from __future__ import annotations

from hypo_gpt.models import HypothesisV2


async def critique_domain(hypothesis: HypothesisV2) -> dict:
    violations = []
    if "perpetual motion" in hypothesis.core_claim.lower():
        violations.append("violates conservation constraints")
    verdict = "reject" if violations else "accept"
    if not violations and len(hypothesis.causal_chain.intermediate.split()) < 15:
        verdict = "revise"
    return {
        "domain_verdict": verdict,
        "violations": violations,
        "strongest_objection": "Mechanism needs clearer boundary conditions." if verdict != "accept" else "No hard physics violation observed.",
    }
