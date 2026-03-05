"""Layer 3 — Adversarial Tribunal.

For N cycles: 4 critics per hypothesis -> mechanism validation ->
verdict -> evolve "revise" -> remove "abandon" -> convergence check.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import structlog

from hypo_claude.agents.evolver import EvolverAgent
from hypo_claude.agents.tribunal import TribunalPanel
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import ResearchLandscape, StructuredHypothesis, TribunalVerdict

logger = structlog.get_logger(__name__)


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 3: Iterative adversarial refinement."""

    hypothesis_pool: list[StructuredHypothesis] = state["hypothesis_pool"]
    landscape: ResearchLandscape = state["research_landscape"]
    config = state.get("config")
    max_cycles = config.tribunal_cycles if config else 3
    max_concurrent = config.max_concurrent_critics if hasattr(config, "max_concurrent_critics") else 4

    panel = TribunalPanel(llm)
    evolver = EvolverAgent(llm)

    current_pool = list(hypothesis_pool)
    all_verdicts: dict[str, TribunalVerdict] = {}
    advanced_total: list[StructuredHypothesis] = []

    for cycle in range(max_cycles):
        if not current_pool:
            break

        if progress:
            await progress(
                "tribunal",
                f"Tribunal cycle {cycle + 1}/{max_cycles} — evaluating {len(current_pool)} hypotheses",
                cycle, max_cycles,
            )

        # Evaluate all hypotheses in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _evaluate(
            h: StructuredHypothesis
        ) -> tuple[StructuredHypothesis, TribunalVerdict | None, Exception | None]:
            async with semaphore:
                try:
                    verdict = await panel.evaluate(h, landscape)
                    return h, verdict, None
                except Exception as exc:
                    return h, None, exc

        results = await asyncio.gather(
            *[_evaluate(h) for h in current_pool],
            return_exceptions=True,
        )

        # Process verdicts
        advance: list[StructuredHypothesis] = []
        revise: list[tuple[StructuredHypothesis, TribunalVerdict]] = []
        abandoned = 0

        for result in results:
            if isinstance(result, Exception):
                logger.error("tribunal.eval_failed", error=str(result))
                continue
            h, verdict, error = result
            if error is not None:
                logger.error("tribunal.eval_failed", hypothesis_id=h.id, error=str(error))
                # Preserve hypotheses when external rate limits/transient errors happen.
                # This avoids collapsing to a single candidate because of API throttling.
                advance.append(h)
                continue

            if verdict is None:
                logger.error("tribunal.eval_failed", hypothesis_id=h.id, error="missing verdict")
                advance.append(h)
                continue
            all_verdicts[h.id] = verdict

            if verdict.overall_verdict == "advance":
                advance.append(h)
            elif verdict.overall_verdict == "revise":
                revise.append((h, verdict))
            else:
                abandoned += 1

        logger.info(
            "tribunal.cycle_done",
            cycle=cycle + 1,
            advanced=len(advance),
            revising=len(revise),
            abandoned=abandoned,
        )
        advanced_total.extend(advance)

        # Evolve "revise" hypotheses
        evolved: list[StructuredHypothesis] = []
        if revise:
            evolve_tasks = [evolver.evolve(h, v) for h, v in revise]
            evolve_results = await asyncio.gather(*evolve_tasks, return_exceptions=True)
            for result in evolve_results:
                if isinstance(result, StructuredHypothesis):
                    evolved.append(result)
                elif isinstance(result, Exception):
                    logger.warning("tribunal.evolve_failed", error=str(result))

        # Next cycle pool = evolved hypotheses only (advanced are done)
        current_pool = evolved

        # Early convergence: if no hypotheses need revision, stop
        if not evolved:
            logger.info("tribunal.converged", cycle=cycle + 1)
            break

    # Final pool: all advanced across cycles + last evolved batch
    refined_by_id: dict[str, StructuredHypothesis] = {}
    for hypothesis in [*advanced_total, *current_pool]:
        refined_by_id[hypothesis.id] = hypothesis
    refined = list(refined_by_id.values())

    if progress:
        await progress("tribunal", f"Tribunal complete: {len(refined)} hypotheses survived", max_cycles, max_cycles)

    return {
        "tribunal_verdicts": all_verdicts,
        "refined_hypotheses": refined,
        "refinement_cycle": cycle + 1,  # type: ignore[possibly-undefined]
    }
