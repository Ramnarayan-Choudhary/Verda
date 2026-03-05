"""Stage 6 — Tournament Ranking with Elo scoring.

Fix: Parallelized pairwise judging with semaphore control.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from vreda_hypothesis.agents import TournamentJudge
from vreda_hypothesis.models import EnhancedHypothesis, PipelineState, StageError
from vreda_hypothesis.runtime import PipelineRuntime
from vreda_hypothesis.utils import elo

logger = structlog.get_logger(__name__)

MAX_CONCURRENT_JUDGES = 8


async def run(state: PipelineState, runtime: PipelineRuntime) -> dict[str, Any]:
    hypotheses = state.refined_hypotheses
    if not hypotheses:
        return {}

    judge = TournamentJudge(runtime.llm)
    ratings = dict(state.elo_ratings) or {hyp.id: elo.DEFAULT_ELO for hyp in hypotheses}
    pairs = elo.select_tournament_pairs([hyp.id for hyp in hypotheses], ratings, n_rounds=state.config.tournament_rounds)

    hyp_lookup = {hyp.id: hyp for hyp in hypotheses}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_JUDGES)

    async def _judge_pair(pair: tuple[str, str]) -> tuple[str, str, str] | None:
        hyp_a_id, hyp_b_id = pair
        hyp_a = hyp_lookup.get(hyp_a_id)
        hyp_b = hyp_lookup.get(hyp_b_id)
        if not hyp_a or not hyp_b:
            return None
        async with semaphore:
            decision = await judge.decide(hyp_a, hyp_b)
            return (hyp_a_id, hyp_b_id, decision.winner)

    try:
        # Run all pairwise judgments in parallel (semaphore-bounded)
        raw_results = await asyncio.gather(*[_judge_pair(pair) for pair in pairs])
        results = [r for r in raw_results if r is not None]

        updated_ratings = elo.run_tournament_sync([hyp.id for hyp in hypotheses], results, initial_ratings=ratings)
        for hyp in hypotheses:
            hyp.elo_rating = updated_ratings.get(hyp.id, hyp.elo_rating)

        ranked = sorted(hypotheses, key=lambda item: item.elo_rating, reverse=True)
        logger.info("stage.tournament.complete", matches=len(results), finalists=len(ranked))
        return {"tournament_results": ranked, "elo_ratings": updated_ratings}
    except Exception as exc:
        logger.exception("stage.tournament.error", error=str(exc))
        state.errors.append(StageError(stage="tournament", message=str(exc)))
        return {"errors": state.errors}
