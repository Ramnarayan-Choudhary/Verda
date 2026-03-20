from __future__ import annotations

import asyncio
import re
from statistics import mean
from typing import Any

from hypo_gpt.layer3_tribunal.tribunal import run_tribunal
from hypo_gpt.models import (
    DevilsAdvocate,
    DimensionScores,
    DomainCritique,
    HypothesisV2,
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
    async def _domain_critic(self, hypothesis: HypothesisV2) -> dict[str, Any]:
        mechanism_specific = len(hypothesis.causal_chain.intermediate.split()) >= 15
        violations: list[str] = []
        if "perpetual motion" in hypothesis.core_claim.lower():
            violations.append("violates basic conservation constraints")
        verdict = "accept" if not violations and mechanism_specific else "revise"
        if violations:
            verdict = "reject"
        return {
            "domain_verdict": verdict,
            "violations": violations,
            "strongest_objection": (
                "The claim requires a clearer causal mediator and boundary condition checks."
                if verdict != "accept"
                else "No direct first-principles violation identified."
            ),
        }

    async def _methodology_critic(self, hypothesis: HypothesisV2) -> dict[str, Any]:
        confounds: list[str] = []
        if "baseline" not in hypothesis.experiment.baseline.lower():
            confounds.append("baseline comparison is underspecified")
        if not _has_quantitative_claim(hypothesis.experiment.success_threshold):
            confounds.append("success threshold lacks quantitative bounds")

        verdict = "accept" if not confounds else "revise"
        return {
            "method_verdict": verdict,
            "confounds": confounds,
            "design_flaws": [] if "ablation" in hypothesis.experiment.design.lower() else ["missing ablation ladder"],
            "improved_design": "Use equal-compute ablation ladder with stress-suite split and repeated seeds.",
        }

    async def _adversarial_critic(self, hypothesis: HypothesisV2) -> dict[str, Any]:
        steelman = (
            "A strong counterargument is that the measured gains could be explained by a hidden confounder such as data curation, "
            "training schedule, or evaluation leakage rather than the claimed mechanism. Without explicit mediator readouts and "
            "factorized ablation controls, observed improvements may be correlation artifacts that fail under regime shift."
        )
        return {
            "adversarial_verdict": "revise" if len(steelman.split()) >= 50 else "accept",
            "steelman_against": steelman,
            "attack_vector": "Confounder-driven performance uplift",
            "rebuttal_needed": "Isolate mediator and verify effect under controlled ablations.",
        }

    async def _resource_critic(self, hypothesis: HypothesisV2) -> dict[str, Any]:
        feasible = _compute_budget_to_score(hypothesis.experiment.compute_estimate)
        has_data = "public" in hypothesis.experiment.required_data.lower()
        verdict = "accept" if feasible >= 0.65 and has_data else "revise"
        return {
            "resource_verdict": verdict,
            "blocking_issues": [] if verdict == "accept" else ["data availability or compute realism unclear"],
            "gpu_hours": hypothesis.experiment.compute_estimate,
            "data_availability": has_data,
            "time_horizon_realistic": hypothesis.experiment.time_horizon in {"1_month", "3_months", "6_months", "12months_plus"},
        }

    async def _executability_critic(self, hypothesis: HypothesisV2) -> dict[str, Any]:
        files_to_modify = 5 if "baseline" in hypothesis.experiment.baseline.lower() else 7
        risk = "low" if files_to_modify <= 5 else "medium"
        if "new infrastructure" in hypothesis.experiment.design.lower():
            risk = "high"
        return {
            "exec_verdict": "accept" if risk != "high" else "revise",
            "files_to_modify": files_to_modify,
            "required_libs": ["numpy", "pytorch", "datasets"],
            "implementation_risk": risk,
        }

    def _mechanism_validator(self, hypothesis: HypothesisV2) -> dict[str, Any]:
        gaps: list[str] = []
        contradictions: list[str] = []

        if len(hypothesis.causal_chain.intermediate.split()) < 15:
            gaps.append("intermediate mechanism is too shallow")
        if not hypothesis.causal_chain.conditions:
            gaps.append("missing boundary conditions")
        if not _has_quantitative_claim(hypothesis.falsification_criterion):
            gaps.append("falsification criterion lacks numeric threshold")

        conditions = " ".join(hypothesis.causal_chain.conditions).lower()
        breaks = " ".join(hypothesis.causal_chain.breaks_when).lower()
        if "always" in conditions and "always" in breaks:
            contradictions.append("conditions and breaks_when both claim unconditional behavior")

        coherence = max(0.0, 1.0 - (0.18 * len(gaps)) - (0.25 * len(contradictions)))
        return {
            "coherence_score": round(coherence, 4),
            "gaps": gaps,
            "contradictions": contradictions,
            "is_logically_valid": coherence >= 0.55 and not contradictions,
        }

    def _mutate_for_cycle(self, hypothesis: HypothesisV2, *, cycle: int) -> HypothesisV2:
        updated = hypothesis.model_copy(deep=True)
        updated.mutation_operator = {1: "deepen_mechanism", 2: "narrow_scope", 3: "sharpen_falsify"}.get(cycle, "none")

        if cycle == 1:
            updated.causal_chain.intermediate = (
                f"{updated.causal_chain.intermediate} Explicit mediator instrumentation now links intervention to outcome under shift."
            )
        elif cycle == 2:
            updated.experiment.required_data = "Public benchmark with open splits and available preprocessing pipeline"
            updated.experiment.compute_estimate = "4xA100 for 20h"
        elif cycle == 3 and not _has_quantitative_claim(updated.falsification_criterion):
            updated.falsification_criterion = (
                "Hypothesis is disproved if primary_metric is < 1.01x baseline under equal-compute stress condition."
            )
        return updated

    async def review_hypothesis_v2(self, hypothesis: HypothesisV2, max_reentry_attempts: int = 2) -> tuple[HypothesisV2 | None, dict[str, Any]]:
        working = hypothesis
        cycle = 0
        final_bundle: dict[str, Any] = {}

        while cycle <= max_reentry_attempts:
            final_bundle = await run_tribunal(working)
            mechanism = final_bundle["mechanism"]
            final_bundle["cycle"] = cycle

            if mechanism["is_logically_valid"]:
                return working, final_bundle

            cycle += 1
            if cycle > max_reentry_attempts:
                break
            working = self._mutate_for_cycle(working, cycle=cycle)

        return None, final_bundle

    def to_legacy_verdict(self, hypothesis: StructuredHypothesis) -> TribunalVerdict:
        mechanism_len = len(hypothesis.mechanism.split())
        mechanism_is_specific = mechanism_len >= 18
        has_quant = _has_quantitative_claim(hypothesis.prediction) and _has_quantitative_claim(
            hypothesis.minimum_viable_test.success_threshold
        )
        feasibility_score = _compute_budget_to_score(hypothesis.minimum_viable_test.estimated_compute)

        domain = DomainCritique(
            is_physically_possible=True,
            domain_validity_score=max(0.45, min(0.92, 0.62 + (0.14 if mechanism_is_specific else 0.0) + (0.06 if has_quant else 0.0))),
            specific_concerns=(
                "Cross-regime transfer assumptions require boundary tests."
                if hypothesis.generation_strategy in {"domain_bridge", "constraint_relaxer", "falsification_designer"}
                else "No obvious first-principles violations; validate with stress checks."
            ),
        )

        confounds: list[str] = []
        if "equal compute" not in hypothesis.minimum_viable_test.baseline.lower():
            confounds.append("baseline may not control for compute parity")
        if not has_quant:
            confounds.append("prediction lacks explicit quantitative threshold")

        methodology = MethodologyCritique(
            experiment_is_valid=True,
            confounds_identified=confounds,
            control_issues=["missing causal ablation"] if "ablation" not in hypothesis.falsification_criterion.lower() else [],
            metric_concerns="Pair headline metric with calibration and robustness diagnostics.",
            suggested_redesign="Add held-out stress suite and strict equal-compute ablation ladder.",
        )

        adversary = DevilsAdvocate(
            strongest_objection=(
                "Observed gains may stem from schedule side effects instead of proposed mechanism."
            ),
            counter_evidence="Similar gains appear with simpler regularization controls.",
            null_hypothesis="Improvements come from hidden confounders rather than mechanism-targeted intervention.",
            rebuttal_possibility="Isolate mechanism with factorized ablations and stress sweeps.",
        )

        resource = ResourceCritique(
            compute_realistic=True,
            data_available=True,
            timeline_estimate=hypothesis.minimum_viable_test.estimated_timeline,
            blocking_conditions=[] if feasibility_score >= 0.65 else ["requires higher GPU budget than standard envelope"],
            feasibility_score=feasibility_score,
        )

        mech = MechanismValidation(
            causal_chain_complete=mechanism_is_specific,
            identified_gaps=[] if mechanism_is_specific else ["missing intermediate causal variable and measurement hook"],
            strengthened_mechanism=(
                hypothesis.mechanism
                if mechanism_is_specific
                else f"{hypothesis.mechanism} Add explicit mediator variable with pre/post readout."
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
            updated.prediction = "Only proceed if stress-suite gains exceed >=3% under equal compute; otherwise terminate."
        else:
            updated.prediction = "Primary metric improves by >=6% and robustness drift remains <=2% across stress splits."
        updated.falsification_criterion = (
            f"{updated.falsification_criterion} Hard fail if causal ablation cannot reproduce the claimed effect."
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

    @staticmethod
    def summarize_bundle(bundle: dict[str, Any]) -> float:
        scores = [
            1.0 if bundle.get("domain", {}).get("domain_verdict") == "accept" else 0.6,
            1.0 if bundle.get("methodology", {}).get("method_verdict") == "accept" else 0.6,
            1.0 if bundle.get("resource", {}).get("resource_verdict") == "accept" else 0.6,
            1.0 if bundle.get("executability", {}).get("exec_verdict") == "accept" else 0.6,
            bundle.get("mechanism", {}).get("coherence_score", 0.5),
        ]
        return round(mean(scores), 4)
