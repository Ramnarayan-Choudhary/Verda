"""Integration tests for Stage 4 — Parallel Filtering."""

from __future__ import annotations

import pytest

from vreda_hypothesis.knowledge.graph import PaperKnowledgeGraph
from vreda_hypothesis.models import (
    HypothesisSeed,
    HypothesisType,
    PaperMetadata,
    PipelineConfig,
    PipelineState,
    ScoredSeed,
)
from vreda_hypothesis.stages import filtering


@pytest.mark.asyncio
async def test_filtering_scores_and_ranks_seeds(
    mock_runtime, sample_seeds, sample_paper_metadata, mock_vector_store
):
    """Full filtering: novelty + budget + verifiability → ranked scored seeds."""
    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(top_k=3),
        seeds=sample_seeds,
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    result = await filtering.run(state, mock_runtime)

    assert "filtered_seeds" in result
    filtered = result["filtered_seeds"]
    assert len(filtered) > 0
    assert all(isinstance(s, ScoredSeed) for s in filtered)

    # Each scored seed should have scores populated
    for scored in filtered:
        assert scored.novelty_score >= 0
        assert scored.verifiability_score >= 0
        assert scored.budget_estimate_usd >= 0
        assert scored.combined_score >= 0

    # Should be sorted by combined_score descending
    scores = [s.combined_score for s in filtered]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_filtering_skips_empty_seeds(mock_runtime):
    """Should return empty dict when no seeds provided."""
    state = PipelineState(config=PipelineConfig())
    result = await filtering.run(state, mock_runtime)
    assert result == {}


@pytest.mark.asyncio
async def test_filtering_uses_verifiability_role(
    mock_runtime, sample_seeds, sample_paper_metadata, mock_vector_store
):
    """Verify LLM verifiability calls use AgentRole.VERIFIABILITY."""
    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(top_k=3),
        seeds=sample_seeds[:2],  # Use fewer seeds for faster test
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    await filtering.run(state, mock_runtime)

    json_calls = [c for c in mock_runtime.llm.call_log if c["method"] == "generate_json"]
    # Should have one explicit VerifiabilityPayload call per seed
    verifiability_calls = [c for c in json_calls if c["model_class"] == "VerifiabilityPayload"]
    assert len(verifiability_calls) == 2


@pytest.mark.asyncio
async def test_filtering_respects_top_k_limit(
    mock_runtime, sample_paper_metadata, mock_vector_store
):
    """Should limit output to config.top_k * 5 or 100."""
    # Create many seeds
    seeds = [
        HypothesisSeed(
            id=f"seed-bulk{i:03d}",
            text=f"Hypothesis about optimization technique {i}",
            type=HypothesisType.EFFICIENCY_OPTIMIZATION,
        )
        for i in range(30)
    ]

    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(top_k=3),  # limit = max(3*5, 20) = 20
        seeds=seeds,
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    result = await filtering.run(state, mock_runtime)
    filtered = result["filtered_seeds"]
    assert len(filtered) <= 20


@pytest.mark.asyncio
async def test_filtering_uses_heuristic_fallback_when_llm_unavailable(
    mock_runtime, sample_seeds, sample_paper_metadata, mock_vector_store
):
    """Filtering should keep operating with heuristic scoring if LLM checks fail."""
    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, source="primary")

    async def _always_fail(*a, **kw):
        raise RuntimeError("forced-filter-llm-failure")

    mock_runtime.llm.generate_json = _always_fail

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(top_k=3),
        seeds=sample_seeds[:3],
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )
    result = await filtering.run(state, mock_runtime)
    assert "filtered_seeds" in result
    assert len(result["filtered_seeds"]) >= 1


def test_budget_to_score_thresholds():
    """Test the budget-to-score mapping thresholds."""
    assert filtering._budget_to_score(3.0) == 1.0
    assert filtering._budget_to_score(10.0) == 0.7
    assert filtering._budget_to_score(30.0) == 0.4
    assert filtering._budget_to_score(80.0) == 0.2
    assert filtering._budget_to_score(200.0) == 0.05
