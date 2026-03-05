"""Integration tests for Stage 6 — Tournament Ranking."""

from __future__ import annotations

import pytest

from vreda_hypothesis.models import (
    EnhancedHypothesis,
    PipelineConfig,
    PipelineState,
)
from vreda_hypothesis.stages import tournament


@pytest.mark.asyncio
async def test_tournament_ranks_hypotheses(mock_runtime, sample_hypotheses):
    """Full tournament: generate pairs → judge → update Elo → rank."""
    elo_ratings = {hyp.id: hyp.elo_rating for hyp in sample_hypotheses}

    state = PipelineState(
        config=PipelineConfig(tournament_rounds=2),
        refined_hypotheses=sample_hypotheses,
        elo_ratings=elo_ratings,
    )

    result = await tournament.run(state, mock_runtime)

    assert "tournament_results" in result
    ranked = result["tournament_results"]
    assert len(ranked) == len(sample_hypotheses)
    assert all(isinstance(h, EnhancedHypothesis) for h in ranked)

    # Should be sorted by Elo rating descending
    elo_values = [h.elo_rating for h in ranked]
    assert elo_values == sorted(elo_values, reverse=True)

    # Elo ratings should be updated
    assert "elo_ratings" in result
    updated = result["elo_ratings"]
    # At least some ratings should have changed from defaults
    assert len(updated) == len(sample_hypotheses)


@pytest.mark.asyncio
async def test_tournament_skips_empty(mock_runtime):
    """Should return empty dict when no hypotheses."""
    state = PipelineState(config=PipelineConfig())
    result = await tournament.run(state, mock_runtime)
    assert result == {}


@pytest.mark.asyncio
async def test_tournament_uses_judge_role(mock_runtime, sample_hypotheses):
    """Verify the tournament judge uses AgentRole.TOURNAMENT_JUDGE."""
    elo_ratings = {hyp.id: 1500.0 for hyp in sample_hypotheses}

    state = PipelineState(
        config=PipelineConfig(tournament_rounds=1),
        refined_hypotheses=sample_hypotheses,
        elo_ratings=elo_ratings,
    )

    await tournament.run(state, mock_runtime)

    json_calls = [c for c in mock_runtime.llm.call_log if c["method"] == "generate_json"]
    judge_calls = [c for c in json_calls if c["role"] == "tournament_judge"]
    assert len(judge_calls) >= 1
    assert all(c["model_class"] == "TournamentDecision" for c in judge_calls)


@pytest.mark.asyncio
async def test_tournament_single_hypothesis(mock_runtime):
    """Tournament with only 1 hypothesis should return it unchanged."""
    hyp = EnhancedHypothesis(id="hyp-solo", title="Solo Hypothesis", elo_rating=1500.0)
    state = PipelineState(
        config=PipelineConfig(tournament_rounds=1),
        refined_hypotheses=[hyp],
        elo_ratings={"hyp-solo": 1500.0},
    )

    result = await tournament.run(state, mock_runtime)
    # select_tournament_pairs returns [] for < 2 hypotheses, so no matches happen
    ranked = result.get("tournament_results", [])
    assert len(ranked) == 1
    assert ranked[0].id == "hyp-solo"
