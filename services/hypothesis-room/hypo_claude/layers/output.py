"""Output layer — serialize ResearchPortfolio into GeneratorOutput (TS-compatible)."""

from __future__ import annotations

from typing import Any, Callable

import structlog

from hypo_claude.models import GeneratorOutput, ResearchPortfolio

logger = structlog.get_logger(__name__)


async def run(state: dict[str, Any], llm: Any = None, progress: Callable | None = None) -> dict[str, Any]:
    """Final layer: Serialize portfolio into TS-frontend-compatible output."""

    portfolio: ResearchPortfolio | None = state.get("research_portfolio")
    landscape = state.get("research_landscape")
    refinement_cycle = state.get("refinement_cycle", 0)

    if progress:
        await progress("output", "Serializing final output...", 0, 1)

    # Build backward-compatible hypothesis list for TS frontend
    hypotheses_list: list[dict] = []
    if portfolio:
        for ph in portfolio.hypotheses:
            h = ph.hypothesis
            hypotheses_list.append({
                "id": h.id,
                "title": h.title,
                "condition": h.condition,
                "intervention": h.intervention,
                "prediction": h.prediction,
                "mechanism": h.mechanism,
                "falsification_criterion": h.falsification_criterion,
                "generation_strategy": h.generation_strategy,
                "portfolio_slot": ph.portfolio_slot,
                "panel_composite": ph.panel_composite,
                "suggested_timeline": ph.suggested_timeline,
                "success_definition": ph.success_definition,
                "failure_learning": ph.failure_learning,
                "minimal_test": h.minimal_test.model_dump(),
                "novelty_claim": h.novelty_claim,
                "closest_existing_work": h.closest_existing_work,
            })

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

    if progress:
        await progress("output", f"Done — {len(hypotheses_list)} hypotheses in portfolio", 1, 1)

    return {"final_output": output}
