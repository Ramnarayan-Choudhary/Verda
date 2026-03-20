from __future__ import annotations

from hypo_gpt.assessment.assessment_agent import EXEC_PROMPT
from hypo_gpt.models import HypothesisV2


async def critique_executability(hypothesis: HypothesisV2) -> dict:
    files_to_modify = 5 if "baseline" in hypothesis.experiment.baseline.lower() else 7
    risk = "low" if files_to_modify <= 5 else "medium"
    return {
        "exec_prompt_used": EXEC_PROMPT,
        "exec_verdict": "accept" if risk != "high" else "revise",
        "files_to_modify": files_to_modify,
        "required_libs": ["numpy", "pytorch", "datasets"],
        "implementation_risk": risk,
    }
