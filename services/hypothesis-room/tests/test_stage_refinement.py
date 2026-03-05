"""Integration tests for Stage 5 — Multi-Agent Refinement Loop."""

from __future__ import annotations

import pytest

from vreda_hypothesis.knowledge.graph import PaperKnowledgeGraph
from vreda_hypothesis.models import (
    EnhancedHypothesis,
    PaperMetadata,
    PipelineConfig,
    PipelineState,
)
from vreda_hypothesis.stages import refinement


@pytest.mark.asyncio
async def test_refinement_produces_hypotheses(
    mock_runtime, sample_scored_seeds, sample_paper_metadata, sample_paper_summary,
    sample_gap_analysis, mock_vector_store
):
    """Full refinement loop: propose → critique → evolve → meta-review."""
    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, summary=sample_paper_summary, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(max_cycles=1, top_k=3),
        paper_metadata=sample_paper_metadata,
        paper_summary=sample_paper_summary,
        gap_analysis=sample_gap_analysis,
        filtered_seeds=sample_scored_seeds,
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    result = await refinement.run(state, mock_runtime)

    assert "refined_hypotheses" in result
    hypotheses = result["refined_hypotheses"]
    assert len(hypotheses) > 0
    assert all(isinstance(h, EnhancedHypothesis) for h in hypotheses)

    # Each hypothesis should have been through critic review
    for hyp in hypotheses:
        assert hyp.critic_assessment is not None
        assert hyp.composite_score > 0
        assert hyp.reflection_rounds_completed >= 1

    # Elo ratings should be populated
    assert "elo_ratings" in result
    assert len(result["elo_ratings"]) > 0

    # Meta review notes should exist
    assert "meta_review_notes" in result

    # Refinement cycle should advance
    assert result["refinement_cycle"] >= 1


@pytest.mark.asyncio
async def test_refinement_skips_without_seeds(mock_runtime):
    """Should return empty dict when no filtered seeds."""
    state = PipelineState(config=PipelineConfig())
    result = await refinement.run(state, mock_runtime)
    assert result == {}


@pytest.mark.asyncio
async def test_refinement_uses_correct_roles(
    mock_runtime, sample_scored_seeds, sample_paper_metadata,
    sample_paper_summary, mock_vector_store
):
    """Verify each agent uses its correct AgentRole."""
    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(max_cycles=1, top_k=2),
        paper_metadata=sample_paper_metadata,
        paper_summary=sample_paper_summary,
        filtered_seeds=sample_scored_seeds[:3],
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    await refinement.run(state, mock_runtime)

    roles_used = {c["role"] for c in mock_runtime.llm.call_log if c["method"] == "generate_json"}
    # Should use proposer, critic, evolver, meta_reviewer roles
    assert "proposer" in roles_used
    assert "critic" in roles_used
    assert "evolver" in roles_used
    assert "meta_reviewer" in roles_used


def test_convergence_detection():
    """Test the Elo convergence check."""
    # Stable ratings → should converge
    prev = {"a": 1500.0, "b": 1520.0, "c": 1480.0}
    current = {"a": 1502.0, "b": 1519.0, "c": 1479.0}
    assert refinement._check_convergence(prev, current) is True

    # Large changes → should not converge
    prev2 = {"a": 1500.0, "b": 1520.0, "c": 1480.0}
    current2 = {"a": 1550.0, "b": 1470.0, "c": 1530.0}
    assert refinement._check_convergence(prev2, current2) is False

    # Empty prev → should not converge
    assert refinement._check_convergence({}, {"a": 1500.0}) is False

    # Too few common IDs → should not converge
    assert refinement._check_convergence({"a": 1500.0}, {"b": 1500.0}) is False


def test_build_context(sample_paper_summary, sample_gap_analysis):
    """Test context string construction."""
    state = PipelineState(
        paper_summary=sample_paper_summary,
        gap_analysis=sample_gap_analysis,
    )
    context = refinement._build_context(state, ["boost novelty"])
    assert "Abstract:" in context
    assert "Methods:" in context
    assert "Known gaps:" in context
    assert "Meta directives:" in context
    assert "boost novelty" in context


def test_gap_summary(sample_gap_analysis):
    """Test gap summary string generation."""
    state = PipelineState(gap_analysis=sample_gap_analysis)
    summary = refinement._gap_summary(state)
    assert "Sparse attention" in summary
    assert "unexplored_direction" in summary

    # No gap analysis → empty
    assert refinement._gap_summary(PipelineState()) == ""
