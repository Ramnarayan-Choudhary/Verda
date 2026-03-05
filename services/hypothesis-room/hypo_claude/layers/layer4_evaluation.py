"""Layer 4 — Multi-Dimensional Panel Evaluation.

3 judges per hypothesis (parallel), 7-axis scoring, rank by composite.
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
    compute_panel_composite,
)

logger = structlog.get_logger(__name__)


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 4: Score and rank hypotheses via 3-judge panel."""

    refined: list[StructuredHypothesis] = state["refined_hypotheses"]
    verdicts: dict[str, TribunalVerdict] = state["tribunal_verdicts"]

    if not refined:
        return {"panel_scores": {}, "ranked_hypotheses": []}

    panel = JudgePanel(llm)
    panel_scores: dict[str, list[JudgeScore]] = {}

    if progress:
        await progress("evaluation", f"Scoring {len(refined)} hypotheses with 3-judge panel...", 0, len(refined))

    # Evaluate all hypotheses (parallel with semaphore)
    semaphore = asyncio.Semaphore(3)

    async def _score(i: int, h: StructuredHypothesis) -> tuple[str, list[JudgeScore]]:
        async with semaphore:
            verdict = verdicts.get(h.id, TribunalVerdict(hypothesis_id=h.id))
            scores = await panel.evaluate(h, verdict)
            if progress:
                await progress("evaluation", f"Scored {h.title[:40]}...", i + 1, len(refined))
            return h.id, scores

    results = await asyncio.gather(
        *[_score(i, h) for i, h in enumerate(refined)],
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, tuple):
            hid, scores = result
            panel_scores[hid] = scores
        elif isinstance(result, Exception):
            logger.error("evaluation.score_failed", error=str(result))

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
    }
