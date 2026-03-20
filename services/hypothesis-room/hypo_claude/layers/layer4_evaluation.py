"""Layer 4 — Multi-Dimensional Panel Evaluation.

3 judges per hypothesis (parallel), 7-axis scoring, controversy detection,
risk-appetite-weighted composites, rank by composite.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import structlog

from hypo_claude.agents.judges import JudgePanel
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import (
    JudgeScore,
    StructuredHypothesis,
    TribunalVerdict,
    compute_controversy_score,
    compute_panel_composite,
)

logger = structlog.get_logger(__name__)


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 4: Score and rank hypotheses via 3-judge panel with controversy detection."""

    refined: list[StructuredHypothesis] = state.get("refined_hypotheses", [])
    verdicts: dict[str, TribunalVerdict] = state.get("tribunal_verdicts", {})
    config = state.get("config")

    if not refined:
        return {"panel_scores": {}, "ranked_hypotheses": [], "controversy_scores": {}}

    panel = JudgePanel(llm)
    panel_scores: dict[str, list[JudgeScore]] = {}
    controversy_scores: dict[str, float] = {}

    if progress:
        await progress("evaluation", f"Scoring {len(refined)} hypotheses with 3-judge panel...", 0, len(refined))

    # Evaluate all hypotheses (parallel with semaphore)
    semaphore = asyncio.Semaphore(3)

    fast_mode = len(refined) <= 7

    async def _score(i: int, h: StructuredHypothesis) -> tuple[str, list[JudgeScore]]:
        async with semaphore:
            verdict = verdicts.get(h.id, TribunalVerdict(hypothesis_id=h.id))
            scores = await panel.evaluate(h, verdict, fast_mode=fast_mode)
            if progress:
                await progress("evaluation", f"Scored {h.title[:40]}...", i + 1, len(refined))
            return h.id, scores

    results = await asyncio.gather(
        *[_score(i, h) for i, h in enumerate(refined)],
        return_exceptions=True,
    )

    for idx, result in enumerate(results):
        if isinstance(result, tuple):
            hid, scores = result
            panel_scores[hid] = scores
            controversy_scores[hid] = compute_controversy_score(scores)
        elif isinstance(result, Exception):
            # Graceful degradation: use tribunal verdict scores as fallback
            h = refined[idx]
            logger.error("evaluation.score_failed", hypothesis=h.title[:40], error=str(result))
            verdict = verdicts.get(h.id)

            # Build fallback DimensionScores from tribunal data
            from hypo_claude.models import DimensionScores
            feas = 50
            mech = 50
            if verdict:
                if verdict.resource_reality:
                    feas = int(getattr(verdict.resource_reality, 'feasibility_score', 0.5) * 100)
                if verdict.mechanism_validation:
                    mech = int(getattr(verdict.mechanism_validation, 'logical_score', 0.5) * 100)

            fallback_dim = DimensionScores(
                mechanistic_quality=mech,
                novelty=50,
                testability=50,
                impact=50,
                feasibility=feas,
                specificity=40,
                creativity=50,
            )
            # Use "generalist" persona — valid Literal value, neutral weight
            fallback_score = JudgeScore(
                judge_persona="generalist",
                scores=fallback_dim,
                rationale="Fallback score — judge panel failed due to rate limiting",
                confidence=0.3,
            )
            panel_scores[h.id] = [fallback_score]
            controversy_scores[h.id] = 0.0
            logger.info("evaluation.fallback_score", hypothesis=h.title[:40], composite=fallback_dim.composite)

    # Log controversy highlights
    controversial = {hid: cs for hid, cs in controversy_scores.items() if cs > 100}
    if controversial:
        logger.info("evaluation.controversial_hypotheses", count=len(controversial))

    # Rank by weighted panel composite
    ranked = sorted(
        refined,
        key=lambda h: compute_panel_composite(panel_scores.get(h.id, [])),
        reverse=True,
    )

    if progress:
        top_score = compute_panel_composite(panel_scores.get(ranked[0].id, [])) if ranked else 0
        await progress("evaluation", f"Evaluation complete. Top score: {top_score:.1f}", len(refined), len(refined))

    return {
        "panel_scores": panel_scores,
        "ranked_hypotheses": ranked,
        "controversy_scores": controversy_scores,
    }
