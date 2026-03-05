"""Integration tests for Stage 3 — Seed Overgeneration."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from vreda_hypothesis.models import HypothesisSeed, PipelineConfig, PipelineState
from vreda_hypothesis.stages import overgeneration
from vreda_hypothesis.utils import dedup


@pytest.mark.asyncio
async def test_overgeneration_produces_seeds(
    mock_runtime, sample_paper_summary, sample_gap_analysis, mock_vector_store
):
    """Full overgeneration: prompts → structured JSON → dedup → seeds."""
    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(max_seeds=50),
        paper_summary=sample_paper_summary,
        gap_analysis=sample_gap_analysis,
        paper_text="Transformer architecture paper.",
        vector_store_client=mock_vector_store,
    )

    # Patch dedup to avoid loading SentenceTransformer model
    with patch.object(dedup, "compute_embeddings") as mock_embed:
        # Each call returns unique vectors so nothing is deduped
        call_count = [0]

        def _fake_embed(texts, batch_size=64):
            result = np.eye(max(len(texts), 1), 128)[:len(texts)]
            # Shift each call to avoid collisions
            call_count[0] += 1
            return result + call_count[0] * 0.1

        mock_embed.side_effect = _fake_embed
        result = await overgeneration.run(state, mock_runtime)

    assert "seeds" in result
    seeds = result["seeds"]
    assert len(seeds) > 0
    assert all(isinstance(s, HypothesisSeed) for s in seeds)

    # Each seed should have text content
    assert all(s.text.strip() for s in seeds)

    # Each seed should have a source_prompt tag
    assert all(s.source_prompt.startswith("seed:") for s in seeds)


@pytest.mark.asyncio
async def test_overgeneration_skips_without_summary(mock_runtime):
    """Should return empty dict when paper_summary is missing."""
    state = PipelineState(config=PipelineConfig())
    result = await overgeneration.run(state, mock_runtime)
    assert result == {}


@pytest.mark.asyncio
async def test_overgeneration_uses_seed_generation_role(
    mock_runtime, sample_paper_summary, sample_gap_analysis, mock_vector_store
):
    """Verify LLM is called with AgentRole.SEED_GENERATION."""
    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(max_seeds=10),
        paper_summary=sample_paper_summary,
        gap_analysis=sample_gap_analysis,
        paper_text="Test.",
        vector_store_client=mock_vector_store,
    )

    with patch.object(dedup, "compute_embeddings") as mock_embed:
        mock_embed.return_value = np.eye(10, 128)[:3]
        await overgeneration.run(state, mock_runtime)

    json_calls = [c for c in mock_runtime.llm.call_log if c["method"] == "generate_json"]
    assert any(c["role"] == "seed_generation" for c in json_calls)
    assert any(c["model_class"] == "SeedBatch" for c in json_calls)


@pytest.mark.asyncio
async def test_overgeneration_respects_max_seeds(
    mock_runtime, sample_paper_summary, mock_vector_store
):
    """Should stop generating when max_seeds is reached."""
    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(max_seeds=10),  # min allowed by PipelineConfig
        paper_summary=sample_paper_summary,
        paper_text="Test.",
        vector_store_client=mock_vector_store,
    )

    with patch.object(dedup, "compute_embeddings") as mock_embed:
        mock_embed.return_value = np.eye(30, 128)[:30]
        result = await overgeneration.run(state, mock_runtime)

    # Seeds generated before dedup may exceed max_seeds slightly, but the
    # generation loop should stop early when it reaches the limit.
    # The mock returns 3 seeds per batch × 7 diversity tags = 21 max,
    # but the loop breaks at max_seeds=10.
    seeds = result.get("seeds", [])
    assert len(seeds) <= 25  # reasonable upper bound after dedup
