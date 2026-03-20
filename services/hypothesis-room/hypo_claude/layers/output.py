"""Output layer — serialize ResearchPortfolio into GeneratorOutput (TS-compatible).

Also stores hypothesis outcomes to cross-session memory for future blocking/building.
"""

from __future__ import annotations

from typing import Any, Callable

import structlog

from hypo_claude.models import GeneratorOutput, ResearchPortfolio, compute_confidence, compute_panel_composite

logger = structlog.get_logger(__name__)


def _hypothesis_text(h) -> str:
    return f"{h.title} {h.condition} {h.intervention} {h.prediction} {h.mechanism}"


async def run(state: dict[str, Any], llm: Any = None, progress: Callable | None = None) -> dict[str, Any]:
    """Final layer: Serialize portfolio + store to memory."""

    portfolio: ResearchPortfolio | None = state.get("research_portfolio")
    landscape = state.get("research_landscape")
    refinement_cycle = state.get("refinement_cycle", 0)

    if progress:
        await progress("output", "Serializing final output...", 0, 2)

    # Build backward-compatible hypothesis list for TS frontend
    panel_scores: dict[str, list] = state.get("panel_scores", {})
    hypotheses_list: list[dict] = []
    if portfolio:
        for ph in portfolio.hypotheses:
            h = ph.hypothesis
            # Compute confidence from judge panel scores for this hypothesis
            h_judges = panel_scores.get(h.id, [])
            confidence = compute_confidence(h_judges) if h_judges else 0.5

            # Per-dimension breakdown for frontend display
            dim_scores = ph.dimension_scores
            entry: dict[str, Any] = {
                "id": h.id,
                "title": h.title,
                "condition": h.condition,
                "intervention": h.intervention,
                "prediction": h.prediction,
                "mechanism": h.mechanism,
                "falsification_criterion": h.falsification_criterion,
                "generation_strategy": h.generation_strategy,
                "portfolio_slot": ph.portfolio_slot,
                "slot_name": ph.slot_name,
                "panel_composite": ph.panel_composite,
                "confidence": round(confidence, 3),
                "controversy_score": ph.controversy_score,
                "dimension_scores": {
                    "mechanistic_quality": dim_scores.mechanistic_quality,
                    "novelty": dim_scores.novelty,
                    "testability": dim_scores.testability,
                    "impact": dim_scores.impact,
                    "feasibility": dim_scores.feasibility,
                    "specificity": dim_scores.specificity,
                    "creativity": dim_scores.creativity,
                    "composite": dim_scores.composite,
                },
                "suggested_timeline": ph.suggested_timeline,
                "success_definition": ph.success_definition,
                "failure_learning": ph.failure_learning,
                "minimal_test": h.minimal_test.model_dump(),
                "novelty_claim": h.novelty_claim,
                "closest_existing_work": h.closest_existing_work,
                "theoretical_basis": h.theoretical_basis,
                "expected_outcome_if_true": h.expected_outcome_if_true,
                "expected_outcome_if_false": h.expected_outcome_if_false,
            }
            if h.causal_chain:
                entry["causal_chain"] = h.causal_chain.model_dump()
            if h.experiment_sketch:
                entry["experiment_sketch"] = h.experiment_sketch.model_dump()
            hypotheses_list.append(entry)

    reasoning_context = ""
    if landscape:
        reasoning_context = (
            f"Research intent: {landscape.research_intent}\n"
            f"Domain: {landscape.intent_domain} / {landscape.intent_subdomain}\n"
            f"Dominant paradigm: {landscape.dominant_paradigm}\n"
            f"Bottleneck hypothesis: {landscape.bottleneck_hypothesis}"
        )

    output = GeneratorOutput(
        hypotheses=hypotheses_list,
        reasoning_context=reasoning_context,
        gap_analysis_used=state.get("research_space_map") is not None,
        reflection_rounds=refinement_cycle,
        generation_strategy="epistemic_engine",
        research_portfolio=portfolio,
        pipeline_version="v2",
    )

    # Store outcomes to memory for future sessions
    memory_store = state.get("memory_store")
    if memory_store and portfolio:
        session_id = state.get("session_id", "")
        domain_tags = []
        if landscape:
            domain_tags = [landscape.intent_domain, landscape.intent_subdomain]
            domain_tags = [t for t in domain_tags if t]

        for ph in portfolio.hypotheses:
            h = ph.hypothesis
            try:
                memory_store.store_outcome(
                    entry_id=h.id,
                    session_id=session_id,
                    hypothesis_title=h.title,
                    hypothesis_text=_hypothesis_text(h),
                    strategy=h.generation_strategy,
                    composite_score=ph.dimension_scores.composite if ph.dimension_scores else 0.0,
                    panel_composite=ph.panel_composite,
                    domain_tags=domain_tags,
                )
            except Exception as e:
                logger.warning("output.memory_store_failed", error=str(e))

        logger.info("output.memory_stored", count=len(portfolio.hypotheses))

    if progress:
        await progress("output", f"Done — {len(hypotheses_list)} hypotheses in portfolio", 2, 2)

    return {"final_output": output}
