from __future__ import annotations

from hypo_gpt.models import (
    DimensionScores,
    GeneratorOutput,
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


def to_generator_output(state: PipelineState) -> GeneratorOutput:
    hypotheses: list[LegacyHypothesis] = []
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
                description=f"{structured.intervention} Condition: {structured.condition}",
                short_hypothesis=f"If {structured.condition}, then {structured.prediction}",
                testable_prediction=structured.prediction,
                expected_outcome=structured.expected_outcome_if_true,
                scores=score,
                composite_score=_composite(score),
                required_modifications=[
                    f"Add strict ablation against baseline: {structured.minimum_viable_test.baseline}",
                    f"Validate on dataset: {structured.minimum_viable_test.dataset}",
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
        },
    )
