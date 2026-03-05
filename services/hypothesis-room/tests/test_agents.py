"""Integration tests for Refinement Agents (Proposer, Critic, Evolver, MetaReviewer, Judge)."""

from __future__ import annotations

import pytest

from vreda_hypothesis.agents import (
    CriticAgent,
    EvolverAgent,
    MetaReviewerAgent,
    ProposerAgent,
    TournamentJudge,
)
from vreda_hypothesis.knowledge.graph import NoveltySignal
from vreda_hypothesis.models import (
    CriticAssessment,
    EnhancedHypothesis,
    HypothesisSeed,
    HypothesisType,
    ScoredSeed,
)


@pytest.mark.asyncio
async def test_proposer_expands_seed(mock_llm):
    """ProposerAgent should expand a seed into a full EnhancedHypothesis."""
    proposer = ProposerAgent(mock_llm)
    seed = HypothesisSeed(
        text="Replace attention with sparse patterns",
        type=HypothesisType.ARCHITECTURE_ABLATION,
    )
    seed_score = ScoredSeed(
        seed=seed,
        novelty_score=0.8,
        budget_estimate_usd=3.0,
        verifiability_score=0.7,
        combined_score=0.75,
    )

    hyp = await proposer.propose(
        seed=seed,
        context="Transformer paper about attention mechanisms",
        gap_summary="Sparse attention underexplored",
        seed_score=seed_score,
    )

    assert isinstance(hyp, EnhancedHypothesis)
    assert hyp.title  # non-empty
    assert hyp.description  # non-empty
    assert hyp.testable_prediction  # non-empty
    assert hyp.composite_score > 0

    # Scores should be blended (0.6 * LLM + 0.4 * seed signal)
    assert hyp.scores.novelty > 0
    assert hyp.scores.feasibility > 0


@pytest.mark.asyncio
async def test_proposer_without_seed_score(mock_llm):
    """ProposerAgent should work without seed_score (uses LLM scores only)."""
    proposer = ProposerAgent(mock_llm)
    seed = HypothesisSeed(text="Test hypothesis seed", type=HypothesisType.SCALE)

    hyp = await proposer.propose(
        seed=seed,
        context="Some context",
        gap_summary="Some gap",
    )

    assert isinstance(hyp, EnhancedHypothesis)
    assert hyp.composite_score > 0


@pytest.mark.asyncio
async def test_critic_reviews_hypothesis(mock_llm):
    """CriticAgent should produce a CriticAssessment."""
    critic = CriticAgent(mock_llm)
    hyp = EnhancedHypothesis(
        id="hyp-test001",
        title="Test Hypothesis",
        description="A test hypothesis about transformers.",
    )
    novelty_signal = NoveltySignal(overlap_ratio=0.3, related_entities=["transformer"], supporting_papers=["Paper A"])

    assessment = await critic.review(hyp, novelty_signal, "Budget: $3.00")

    assert isinstance(assessment, CriticAssessment)
    assert assessment.hypothesis_id == "hyp-test001"
    assert assessment.verdict in {"strong", "viable", "weak"}
    assert assessment.grounding_score >= 0


@pytest.mark.asyncio
async def test_evolver_generates_new_seeds(mock_llm, sample_hypotheses):
    """EvolverAgent should produce new HypothesisSeeds from existing hypotheses."""
    evolver = EvolverAgent(mock_llm)
    seeds = await evolver.evolve(sample_hypotheses[:3], "novelty_boost")

    assert len(seeds) > 0
    assert all(isinstance(s, HypothesisSeed) for s in seeds)
    assert all(s.text.strip() for s in seeds)
    assert all(s.source_prompt.startswith("evolver:") for s in seeds)


@pytest.mark.asyncio
async def test_evolver_empty_input(mock_llm):
    """EvolverAgent should return empty list for empty input."""
    evolver = EvolverAgent(mock_llm)
    seeds = await evolver.evolve([], "any_style")
    assert seeds == []


@pytest.mark.asyncio
async def test_meta_reviewer_generates_directives(mock_llm):
    """MetaReviewerAgent should produce directives from critic notes."""
    meta = MetaReviewerAgent(mock_llm)
    directives = await meta.reflect(
        ["Hypothesis lacks novelty", "Need more cross-domain ideas", "Budget too high"],
        cycle=2,
    )

    assert len(directives.directives) > 0
    assert isinstance(directives.directives[0], str)


@pytest.mark.asyncio
async def test_meta_reviewer_empty_notes(mock_llm):
    """MetaReviewerAgent should return empty directives for empty notes."""
    meta = MetaReviewerAgent(mock_llm)
    directives = await meta.reflect([], cycle=1)
    assert directives.directives == []


@pytest.mark.asyncio
async def test_tournament_judge_decides(mock_llm, sample_hypotheses):
    """TournamentJudge should pick a winner between two hypotheses."""
    judge = TournamentJudge(mock_llm)
    decision = await judge.decide(sample_hypotheses[0], sample_hypotheses[1])

    assert decision.winner in {"a", "b", "tie"}
    assert decision.rationale  # non-empty
