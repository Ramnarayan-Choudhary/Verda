from __future__ import annotations

from hypo_gpt.models import HypothesisV2


async def critique_resource(hypothesis: HypothesisV2) -> dict:
    data_ok = "public" in hypothesis.experiment.required_data.lower()
    verdict = "accept" if data_ok else "revise"
    return {
        "resource_verdict": verdict,
        "blocking_issues": [] if data_ok else ["required data availability unclear"],
        "gpu_hours": hypothesis.experiment.compute_estimate,
        "data_availability": data_ok,
        "time_horizon_realistic": True,
    }
