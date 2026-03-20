from __future__ import annotations

from typing import Any

from hypo_gpt.models import (
    DimensionScores,
    GeneratorOutput,
    GeneratorOutputV2,
    LegacyDimensionScores,
    LegacyHypothesis,
    PipelineState,
)


def _strategy_to_type(strategy: str) -> str:
    mapping = {
        "assumption_challenger": "failure_mode_analysis",
        "domain_bridge": "cross_domain_transfer",
        "contradiction_resolver": "theoretical_extension",
        "constraint_relaxer": "constraint_relaxation",
        "mechanism_extractor": "architecture_ablation",
        "synthesis_catalyst": "combination",
        "falsification_designer": "failure_mode_analysis",
    }
    return mapping.get(strategy, "combination")


def _convert_scores(scores: DimensionScores) -> LegacyDimensionScores:
    return LegacyDimensionScores(
        novelty=round(scores.novelty * 10),
        feasibility=round(scores.feasibility * 10),
        impact=round(scores.scientific_impact * 10),
        grounding=round(scores.mechanistic_quality * 10),
        testability=round(scores.testability * 10),
        clarity=round(scores.specificity * 10),
    )


def _composite(scores: LegacyDimensionScores) -> int:
    return round(
        scores.novelty * 0.25
        + scores.feasibility * 0.20
        + scores.impact * 0.20
        + scores.grounding * 0.15
        + scores.testability * 0.10
        + scores.clarity * 0.10
    )


def _complexity_from_scores(scores: LegacyDimensionScores) -> str:
    if scores.feasibility >= 75 and scores.grounding >= 65:
        return "low"
    if scores.feasibility <= 50 or scores.clarity <= 50:
        return "high"
    return "medium"


def _strategy_to_type_v2(strategy: str) -> str:
    mapping = {
        "gap_fill": "architecture_ablation",
        "cross_domain": "cross_domain_transfer",
        "assumption_challenge": "failure_mode_analysis",
        "method_recomb": "combination",
        "failure_inversion": "failure_mode_analysis",
        "abductive": "theoretical_extension",
        "constraint_relax": "constraint_relaxation",
    }
    return mapping.get(strategy, "combination")


def _legacy_scores_from_panel(verdict: Any) -> LegacyDimensionScores:
    return LegacyDimensionScores(
        novelty=round(max(0.0, min(1.0, verdict.novelty_mean)) * 100),
        feasibility=round(max(0.0, min(1.0, verdict.feasibility_mean)) * 100),
        impact=round(max(0.0, min(1.0, verdict.importance_mean)) * 100),
        grounding=round(max(0.0, min(1.0, verdict.coherence_mean)) * 100),
        testability=round(max(0.0, min(1.0, verdict.executability_mean)) * 100),
        clarity=round(max(0.0, min(1.0, ((0.6 * verdict.executability_mean) + (0.4 * verdict.coherence_mean))) * 100)),
    )


def _compact_condition(text: str) -> str:
    value = " ".join(text.split()).strip()
    value = value.rstrip(".")
    lowered = value.lower()
    if lowered.startswith("if "):
        return value[3:]
    if lowered.startswith("under "):
        return value
    if lowered.startswith("when "):
        return value
    return f"when {value}"


def to_generator_output(state: PipelineState) -> GeneratorOutput:
    hypotheses: list[LegacyHypothesis] = []

    if state.final_portfolio_v2 and state.refined_hypotheses_v2:
        hypo_map = {hypothesis.hypo_id: hypothesis for hypothesis in state.refined_hypotheses_v2}
        for verdict in state.final_portfolio_v2[: state.config.top_k]:
            hypothesis = hypo_map.get(verdict.hypo_id)
            if hypothesis is None:
                continue

            score = _legacy_scores_from_panel(verdict)
            tribunal_bundle = state.tribunal_verdicts_v2.get(hypothesis.hypo_id, {})
            method_confounds = (tribunal_bundle.get("methodology") or {}).get("confounds", [])
            method_design_flaws = (tribunal_bundle.get("methodology") or {}).get("design_flaws", [])
            risk_factors = [str(item) for item in [*method_confounds, *method_design_flaws] if str(item).strip()]
            if not risk_factors:
                risk_factors = ["No critical methodological blockers identified; validate under stress-suite."]

            hypotheses.append(
                LegacyHypothesis(
                    id=hypothesis.hypo_id,
                    type=_strategy_to_type_v2(hypothesis.strategy),
                    title=hypothesis.title,
                    description=(
                        f"Condition: {_compact_condition(hypothesis.problem_being_solved)}. "
                        f"Intervention: {hypothesis.core_claim}. "
                        f"Falsification: {hypothesis.falsification_criterion}"
                    ),
                    short_hypothesis=(
                        f"{_compact_condition(hypothesis.problem_being_solved).capitalize()}, "
                        f"{hypothesis.core_claim[:110]} should cause {hypothesis.causal_chain.outcome}"
                    ),
                    testable_prediction=hypothesis.causal_chain.outcome,
                    expected_outcome=(
                        f"{hypothesis.causal_chain.outcome} (fail condition: {hypothesis.falsification_criterion})"
                    ),
                    scores=score,
                    composite_score=round(max(0.0, min(1.0, verdict.panel_composite)) * 100),
                    required_modifications=[
                        f"Baseline discipline: {hypothesis.experiment.baseline}",
                        f"Experimental design: {hypothesis.experiment.design}",
                        f"Success threshold: {hypothesis.experiment.success_threshold}",
                    ],
                    estimated_complexity=(
                        "low"
                        if verdict.feasibility_mean >= 0.75 and verdict.executability_mean >= 0.75
                        else "high"
                        if verdict.feasibility_mean < 0.50 or verdict.executability_mean < 0.50
                        else "medium"
                    ),
                    evidence_basis={
                        "supporting_papers": hypothesis.grounding_paper_ids[:4],
                        "prior_results": ", ".join(hypothesis.grounding_paper_ids[:2]),
                        "key_insight": hypothesis.causal_chain.intermediate,
                        "gap_exploited": hypothesis.problem_being_solved,
                    },
                    novelty_assessment={
                        "is_novel": verdict.novelty_mean >= 0.55,
                        "similar_work": hypothesis.grounding_paper_ids[:2],
                        "what_is_new": hypothesis.core_claim,
                        "novelty_score": score.novelty,
                        "novelty_type": hypothesis.strategy,
                    },
                    experiment_design={
                        "baseline": {"description": hypothesis.experiment.baseline},
                        "independent_variable": hypothesis.core_claim,
                        "success_metrics": [
                            {
                                "metric_name": hypothesis.experiment.primary_metric,
                                "target_value": hypothesis.experiment.success_threshold,
                            }
                        ],
                        "dataset_requirements": [{"name": hypothesis.experiment.required_data}],
                        "estimated_duration": hypothesis.experiment.time_horizon,
                    },
                    risk_factors=risk_factors,
                    related_work_summary=", ".join(hypothesis.grounding_paper_ids[:2]),
                    addresses_gap_id=hypothesis.tree_node_id or None,
                    critic_assessment={
                        "hypothesis_id": hypothesis.hypo_id,
                        "feasibility_issues": risk_factors,
                        "grounding_score": round(verdict.coherence_mean, 4),
                        "overlap_with_literature": ", ".join(hypothesis.grounding_paper_ids[:2]),
                        "suggested_improvements": [
                            (tribunal_bundle.get("methodology") or {}).get("improved_design", "Run stronger ablation controls."),
                        ],
                        "verdict": "strong" if verdict.panel_composite >= 0.75 else "viable",
                    },
                    reflection_rounds_completed=state.refinement_cycle,
                    archetype=hypothesis.strategy,
                    statement=(
                        f"IF {hypothesis.problem_being_solved} THEN {hypothesis.causal_chain.outcome} "
                        f"BECAUSE {hypothesis.causal_chain.intermediate}"
                    ),
                    mve=[
                        f"Design: {hypothesis.experiment.design}",
                        f"Baseline: {hypothesis.experiment.baseline}",
                        f"Metric: {hypothesis.experiment.primary_metric}",
                        f"Threshold: {hypothesis.experiment.success_threshold}",
                        f"Horizon: {hypothesis.experiment.time_horizon}",
                    ],
                    falsification_threshold=hypothesis.falsification_criterion,
                    portfolio_tag="v2_selected",
                    elo_rating=1500.0 + round(max(0.0, min(1.0, verdict.panel_composite)) * 100),
                )
            )

        return GeneratorOutput(
            hypotheses=hypotheses,
            reasoning_context=(
                f"Layered synthesis complete: docs={len(state.paper_intelligences)}, "
                f"tree_nodes={(len(state.idea_tree.nodes) if state.idea_tree else 0)}, "
                f"panel={len(state.panel_verdicts)}, portfolio={len(state.final_portfolio_v2)}"
            ),
            gap_analysis_used=bool(state.research_space_map),
            reflection_rounds=state.refinement_cycle,
            generation_strategy="knowledge_grounded",
            portfolio_audit={
                "coverage": {f"slot_{idx+1}": item.hypo_id for idx, item in enumerate(state.final_portfolio_v2)},
                "redundancies": [],
                "execution_order": [item.hypo_id for item in state.final_portfolio_v2],
            },
            engine_used="gpt",
            diagnostics={
                "errors": state.errors,
                "high_value_targets": state.research_space_map.high_value_targets if state.research_space_map else [],
                "panel_v2_count": len(state.panel_verdicts),
                "portfolio_v2_count": len(state.final_portfolio_v2),
                "memory_entries": len(state.memory_entries),
            },
        )

    portfolio = state.final_portfolio
    portfolio_items = portfolio.hypotheses if portfolio else []

    for item in portfolio_items[: state.config.top_k]:
        structured = item.hypothesis
        score = _convert_scores(item.dimension_scores)
        hypotheses.append(
            LegacyHypothesis(
                id=structured.id,
                type=_strategy_to_type(structured.generation_strategy),
                title=structured.title,
                description=(
                    f"Condition: {structured.condition}. Intervention: {structured.intervention}. "
                    f"Mechanism: {structured.mechanism}. Falsification: {structured.falsification_criterion}"
                ),
                short_hypothesis=(
                    f"If {structured.condition}, applying '{structured.intervention}' should cause: {structured.prediction}"
                ),
                testable_prediction=structured.prediction,
                expected_outcome=f"{structured.expected_outcome_if_true} (fail condition: {structured.falsification_criterion})",
                scores=score,
                composite_score=_composite(score),
                required_modifications=[
                    f"Add strict ablation against baseline: {structured.minimum_viable_test.baseline}",
                    f"Validate on dataset: {structured.minimum_viable_test.dataset}",
                    f"Enforce falsification gate: {structured.falsification_criterion}",
                ],
                estimated_complexity=_complexity_from_scores(score),
                evidence_basis={
                    "supporting_papers": [],
                    "prior_results": structured.closest_existing_work,
                    "key_insight": structured.mechanism,
                    "gap_exploited": structured.source_gap_id,
                },
                novelty_assessment={
                    "is_novel": True,
                    "similar_work": [structured.closest_existing_work],
                    "what_is_new": structured.novelty_claim,
                    "novelty_score": score.novelty,
                    "novelty_type": "new_combination" if structured.generation_strategy == "synthesis_catalyst" else "new_application",
                },
                experiment_design={
                    "baseline": {"description": structured.minimum_viable_test.baseline},
                    "independent_variable": structured.intervention,
                    "success_metrics": [
                        {
                            "metric_name": structured.minimum_viable_test.primary_metric,
                            "target_value": structured.minimum_viable_test.success_threshold,
                        }
                    ],
                    "dataset_requirements": [{"name": structured.minimum_viable_test.dataset}],
                    "estimated_duration": structured.minimum_viable_test.estimated_timeline,
                },
                risk_factors=item.tribunal_verdict.methodology.confounds_identified,
                related_work_summary=structured.closest_existing_work,
                addresses_gap_id=structured.source_gap_id,
                critic_assessment={
                    "hypothesis_id": structured.id,
                    "feasibility_issues": item.tribunal_verdict.resource_reality.blocking_conditions,
                    "grounding_score": item.dimension_scores.mechanistic_quality / 10,
                    "overlap_with_literature": structured.closest_existing_work,
                    "suggested_improvements": [item.tribunal_verdict.revision_directive],
                    "verdict": "strong" if item.tribunal_verdict.overall_verdict == "advance" else "viable",
                },
                reflection_rounds_completed=state.refinement_cycle,
                archetype="mechanistic_probe",
                statement=f"IF {structured.condition} THEN {structured.prediction} BECAUSE {structured.mechanism}",
                mve=[
                    f"Dataset: {structured.minimum_viable_test.dataset}",
                    f"Baseline: {structured.minimum_viable_test.baseline}",
                    f"Metric: {structured.minimum_viable_test.primary_metric}",
                    f"Threshold: {structured.minimum_viable_test.success_threshold}",
                    f"Timeline: {structured.minimum_viable_test.estimated_timeline}",
                ],
                falsification_threshold=structured.falsification_criterion,
                portfolio_tag=item.portfolio_slot,
                elo_rating=1500.0 + _composite(score),
            )
        )

    return GeneratorOutput(
        hypotheses=hypotheses,
        reasoning_context=(
            f"Layered synthesis complete: docs={len(state.paper_intelligences)}, "
            f"pool={len(state.hypothesis_pool)}, ranked={len(state.ranked_hypotheses)}, "
            f"portfolio={len(portfolio_items)}"
        ),
        gap_analysis_used=bool(state.research_space_map),
        reflection_rounds=state.refinement_cycle,
        generation_strategy="knowledge_grounded",
        portfolio_audit={
            "coverage": {item.portfolio_slot: item.hypothesis.id for item in portfolio_items},
            "redundancies": [],
            "execution_order": portfolio.suggested_execution_order if portfolio else [],
        },
        engine_used="gpt",
        diagnostics={
            "errors": state.errors,
            "high_value_targets": state.research_space_map.high_value_targets if state.research_space_map else [],
            "panel_v2_count": len(state.panel_verdicts),
            "portfolio_v2_count": len(state.final_portfolio_v2),
            "memory_entries": len(state.memory_entries),
        },
    )


def to_generator_output_v2(state: PipelineState) -> GeneratorOutputV2:
    return GeneratorOutputV2(
        hypotheses=list(state.refined_hypotheses_v2),
        panel_verdicts=list(state.panel_verdicts.values()),
        portfolio=list(state.final_portfolio_v2),
        memory_context=state.memory_context,
        reasoning_context=(
            f"Layered v2 synthesis complete: docs={len(state.paper_intelligences)}, "
            f"tree_nodes={(len(state.idea_tree.nodes) if state.idea_tree else 0)}, "
            f"refined={len(state.refined_hypotheses_v2)}, portfolio={len(state.final_portfolio_v2)}"
        ),
        engine_used="gpt",
        diagnostics={
            "errors": state.errors,
            "high_value_targets": state.research_space_map.high_value_targets if state.research_space_map else [],
            "memory_entries": len(state.memory_entries),
        },
    )
