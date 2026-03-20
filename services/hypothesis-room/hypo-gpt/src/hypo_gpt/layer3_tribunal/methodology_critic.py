from __future__ import annotations

from hypo_gpt.models import HypothesisV2


async def critique_methodology(hypothesis: HypothesisV2) -> dict:
    confounds = []
    if "baseline" not in hypothesis.experiment.baseline.lower():
        confounds.append("baseline missing")
    flaws = []
    if "ablation" not in hypothesis.experiment.design.lower():
        flaws.append("missing ablation ladder")
    return {
        "method_verdict": "accept" if not confounds and not flaws else "revise",
        "confounds": confounds,
        "design_flaws": flaws,
        "improved_design": "Use equal-compute baseline plus stress-suite with repeated seeds.",
    }
