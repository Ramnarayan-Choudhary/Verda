from __future__ import annotations

import re

from hypo_gpt.models import (
    DevilsAdvocate,
    DimensionScores,
    DomainCritique,
    MechanismValidation,
    MethodologyCritique,
    ResourceCritique,
    StructuredHypothesis,
    TribunalVerdict,
)


def _has_quantitative_claim(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _compute_budget_to_score(compute: str) -> float:
    lower = compute.lower()
    if "16x" in lower:
        return 0.55
    if "8x" in lower:
        return 0.68
    if "4x" in lower or "2x" in lower:
        return 0.8
    return 0.72


class TribunalAgent:
    def review(self, hypothesis: StructuredHypothesis) -> TribunalVerdict:
        mechanism_len = len(hypothesis.mechanism.split())
        mechanism_is_specific = mechanism_len >= 18
        has_quant = _has_quantitative_claim(hypothesis.prediction) and _has_quantitative_claim(
            hypothesis.minimum_viable_test.success_threshold
        )
        feasibility_score = _compute_budget_to_score(hypothesis.minimum_viable_test.estimated_compute)
        high_risk_strategy = hypothesis.generation_strategy in {"domain_bridge", "constraint_relaxer", "falsification_designer"}

        domain = DomainCritique(
            is_physically_possible=True,
            domain_validity_score=max(0.45, min(0.92, 0.62 + (0.14 if mechanism_is_specific else 0.0) + (0.06 if has_quant else 0.0))),
            specific_concerns=(
                "Cross-regime transfer assumptions require careful boundary tests."
                if high_risk_strategy
                else "No obvious first-principles violations; validate under stronger stress conditions."
            ),
        )

        confounds: list[str] = []
        if "equal compute" not in hypothesis.minimum_viable_test.baseline.lower():
            confounds.append("baseline may not control for compute parity")
        if not has_quant:
            confounds.append("prediction lacks explicit quantitative threshold")
        if "shift" not in hypothesis.condition.lower() and "ood" not in hypothesis.condition.lower():
            confounds.append("condition does not explicitly cover distribution shift")

        methodology = MethodologyCritique(
            experiment_is_valid=True,
            confounds_identified=confounds,
            control_issues=["missing causal ablation"] if "ablation" not in hypothesis.falsification_criterion.lower() else [],
            metric_concerns="Pair headline metric with calibration and shift-robustness diagnostics.",
            suggested_redesign="Add held-out stress suite and strict equal-compute ablation ladder.",
        )
        adversary = DevilsAdvocate(
            strongest_objection=(
                "Observed gains may stem from training schedule side effects, not the proposed mechanism."
            ),
            counter_evidence="Comparable gains have been reported via simpler regularization controls.",
            null_hypothesis="Improvements come from hidden confounders rather than mechanism-targeted intervention.",
            rebuttal_possibility="Isolate mechanism component with factorized ablations and stress-condition sweeps.",
        )
        resource = ResourceCritique(
            compute_realistic=True,
            data_available=True,
            timeline_estimate=hypothesis.minimum_viable_test.estimated_timeline,
            blocking_conditions=[] if feasibility_score >= 0.65 else ["requires higher GPU budget than standard project envelope"],
            feasibility_score=feasibility_score,
        )
        mech = MechanismValidation(
            causal_chain_complete=mechanism_is_specific,
            identified_gaps=[] if mechanism_is_specific else ["missing intermediate causal variable and measurement hook"],
            strengthened_mechanism=(
                hypothesis.mechanism
                if mechanism_is_specific
                else f"{hypothesis.mechanism} Add an explicit mediator variable with pre/post intervention readout."
            ),
            logical_score=max(0.45, min(0.9, 0.56 + (0.2 if mechanism_is_specific else 0.0) + (0.08 if has_quant else 0.0))),
        )

        if not mechanism_is_specific and not has_quant:
            verdict = "abandon"
        elif mechanism_is_specific and feasibility_score >= 0.65:
            verdict = "advance"
        else:
            verdict = "revise"
        return TribunalVerdict(
            hypothesis_id=hypothesis.id,
            domain_validity=domain,
            methodology=methodology,
            devils_advocate=adversary,
            resource_reality=resource,
            mechanism_validation=mech,
            overall_verdict=verdict,
            primary_weakness="mechanism specificity and testability" if verdict != "advance" else "none",
            revision_directive=(
                "add explicit mediator variable, quantitative threshold, and equal-compute ablation"
                if verdict != "advance"
                else "prepare panel evaluation with stress-suite replication"
            ),
        )

    def evolve(self, hypothesis: StructuredHypothesis, verdict: TribunalVerdict) -> StructuredHypothesis:
        if verdict.overall_verdict == "advance":
            return hypothesis
        updated = hypothesis.model_copy(deep=True)
        if verdict.mechanism_validation.strengthened_mechanism:
            updated.mechanism = verdict.mechanism_validation.strengthened_mechanism
        if verdict.overall_verdict == "abandon":
            updated.prediction = (
                "Only proceed if stress-suite gains exceed >=3% under equal compute; otherwise terminate this branch."
            )
        else:
            updated.prediction = (
                "Primary metric improves by >=6% and robustness variance drift remains <=2% across stress splits."
            )
        updated.falsification_criterion = (
            f"{updated.falsification_criterion} Hard fail if causal ablation cannot reproduce claimed effect."
        )
        return updated

    def quick_scores(self, verdict: TribunalVerdict) -> DimensionScores:
        return DimensionScores(
            mechanistic_quality=round(verdict.mechanism_validation.logical_score * 10, 2),
            novelty=7.0 if verdict.overall_verdict == "advance" else 6.2,
            testability=7.4 if verdict.overall_verdict == "advance" else 5.8,
            scientific_impact=7.2 if verdict.overall_verdict != "abandon" else 5.2,
            feasibility=round(verdict.resource_reality.feasibility_score * 10, 2),
            specificity=7.2 if verdict.overall_verdict == "advance" else 6.1,
            creativity=7.1 if verdict.overall_verdict != "abandon" else 5.5,
        )
