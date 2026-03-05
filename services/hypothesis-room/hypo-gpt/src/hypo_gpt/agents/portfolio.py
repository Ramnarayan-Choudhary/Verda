from __future__ import annotations

from hypo_gpt.models import (
    DimensionScores,
    PortfolioHypothesis,
    ResearchPortfolio,
    ResourceSummary,
    StructuredHypothesis,
    TribunalVerdict,
)


class PortfolioConstructor:
    def build(
        self,
        ranked: list[StructuredHypothesis],
        scores: dict[str, DimensionScores],
        verdicts: dict[str, TribunalVerdict],
    ) -> ResearchPortfolio:
        if not ranked:
            return ResearchPortfolio(portfolio_rationale="No ranked hypotheses available.")

        # First pass: prioritize one strong candidate per strategy to enforce diversity.
        diverse_ranked: list[StructuredHypothesis] = []
        seen_strategy: set[str] = set()
        for hyp in ranked:
            if hyp.generation_strategy in seen_strategy:
                continue
            diverse_ranked.append(hyp)
            seen_strategy.add(hyp.generation_strategy)
        for hyp in ranked:
            if hyp.id in {item.id for item in diverse_ranked}:
                continue
            diverse_ranked.append(hyp)

        safe: list[StructuredHypothesis] = []
        medium: list[StructuredHypothesis] = []
        moonshot: list[StructuredHypothesis] = []

        for hyp in diverse_ranked:
            s = scores.get(hyp.id)
            if not s:
                continue
            if s.feasibility >= 7.0 and len(safe) < 2:
                safe.append(hyp)
            elif s.scientific_impact >= 7.0 and len(medium) < 2:
                medium.append(hyp)
            elif s.creativity >= 7.5 and len(moonshot) < 1:
                moonshot.append(hyp)

        selected = safe + medium + moonshot
        deduped_selected: list[StructuredHypothesis] = []
        selected_strategies: set[str] = set()
        for hyp in selected:
            if hyp.generation_strategy in selected_strategies:
                continue
            deduped_selected.append(hyp)
            selected_strategies.add(hyp.generation_strategy)
        selected = deduped_selected

        if len(selected) < 4:
            for hyp in diverse_ranked:
                if hyp.id not in {x.id for x in selected}:
                    if hyp.generation_strategy in {x.generation_strategy for x in selected} and len(selected) < 3:
                        continue
                    selected.append(hyp)
                if len(selected) >= 5:
                    break

        portfolio_hypotheses: list[PortfolioHypothesis] = []
        for idx, hyp in enumerate(selected[:5]):
            if hyp in safe:
                slot = "safe"
            elif hyp in medium:
                slot = "medium"
            elif hyp in moonshot:
                slot = "moonshot"
            else:
                slot = "medium"
            score = scores.get(hyp.id) or DimensionScores()
            verdict = verdicts.get(hyp.id)
            if verdict is None:
                continue
            portfolio_hypotheses.append(
                PortfolioHypothesis(
                    hypothesis=hyp,
                    portfolio_slot=slot,
                    dimension_scores=score,
                    tribunal_verdict=verdict,
                    portfolio_position_rationale=f"Placed in {slot} slot based on impact-feasibility profile.",
                    suggested_timeline=hyp.minimum_viable_test.estimated_timeline,
                    dependencies=[],
                    success_definition=hyp.minimum_viable_test.success_threshold,
                    failure_learning=hyp.expected_outcome_if_false,
                )
            )

        execution_order = [item.hypothesis.id for item in sorted(portfolio_hypotheses, key=lambda p: p.suggested_timeline)]
        compute_hours = 12.0 * len(portfolio_hypotheses)

        return ResearchPortfolio(
            hypotheses=portfolio_hypotheses,
            portfolio_rationale="Balanced across feasibility, impact, and creative upside.",
            suggested_execution_order=execution_order,
            resource_summary=ResourceSummary(
                estimated_compute_hours=compute_hours,
                timeline_summary="Execute safe hypotheses first, then medium, then moonshot validation.",
                data_dependencies=[item.hypothesis.minimum_viable_test.dataset for item in portfolio_hypotheses],
            ),
        )
