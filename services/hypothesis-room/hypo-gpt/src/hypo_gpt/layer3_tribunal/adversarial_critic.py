from __future__ import annotations

from hypo_gpt.models import HypothesisV2


async def critique_adversarial(hypothesis: HypothesisV2) -> dict:
    steelman = (
        "Observed gains may come from hidden training or evaluation confounders rather than the claimed mechanism. "
        "Without mediator-level instrumentation and controlled ablations, this could fail under deployment shift. "
        "A robust rebuttal must isolate causal contribution and replicate across stress splits with compute parity."
    )
    return {
        "adversarial_verdict": "revise" if len(steelman.split()) >= 50 else "accept",
        "steelman_against": steelman,
        "attack_vector": "confounder-driven gains",
        "rebuttal_needed": "Add mediator probes and factorized ablations.",
    }
