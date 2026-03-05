"""Integration tests for Stage 1 — Paper Ingestion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from vreda_hypothesis.knowledge.graph import PaperKnowledgeGraph
from vreda_hypothesis.models import PaperMetadata, PaperSummary, PipelineConfig, PipelineState
from vreda_hypothesis.stages import ingestion


@pytest.mark.asyncio
async def test_ingestion_with_arxiv_id(mock_runtime):
    """Full ingestion from arXiv ID: fetch → extract → summarize → KG + vector store."""
    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(max_seeds=20),
    )

    # Patch PDF extraction to avoid needing a real PDF
    with patch.object(ingestion, "_extract_pdf_text", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = (
            "We propose a new network architecture, the Transformer, based solely on attention mechanisms. "
            "The Transformer uses self-attention to compute representations of its input and output."
        )
        result = await ingestion.run(state, mock_runtime)

    assert "paper_metadata" in result
    assert "paper_summary" in result
    assert "text_chunks" in result
    assert "knowledge_graph" in result

    metadata = result["paper_metadata"]
    assert isinstance(metadata, PaperMetadata)
    assert metadata.arxiv_id == "1706.03762"

    summary = result["paper_summary"]
    assert isinstance(summary, PaperSummary)
    assert summary.title  # non-empty
    assert summary.domain  # non-empty

    # Knowledge graph initialized with primary paper
    graph = result["knowledge_graph"]
    assert isinstance(graph, PaperKnowledgeGraph)
    assert graph.graph.number_of_nodes() >= 1

    # Chunks stored in vector store
    assert len(result["text_chunks"]) > 0


@pytest.mark.asyncio
async def test_ingestion_with_pdf_path(mock_runtime, tmp_path):
    """Ingestion from local PDF path."""
    pdf_file = tmp_path / "test_paper.pdf"
    pdf_file.write_bytes(b"%PDF-1.0 minimal test content")

    state = PipelineState(
        pdf_path=str(pdf_file),
        config=PipelineConfig(),
    )

    with patch.object(ingestion, "_extract_pdf_text", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = "Test paper content about transformer models."
        result = await ingestion.run(state, mock_runtime)

    assert "paper_metadata" in result
    # PDF path uses filename as title when no arXiv metadata
    metadata = result["paper_metadata"]
    assert metadata.title == "test_paper"


@pytest.mark.asyncio
async def test_ingestion_missing_source(mock_runtime):
    """Should return error when neither arxiv_id nor pdf_path provided."""
    state = PipelineState(config=PipelineConfig())
    result = await ingestion.run(state, mock_runtime)

    # Should have errors
    assert "errors" in result
    assert len(result["errors"]) > 0
    assert result["errors"][0].stage == "ingestion"


@pytest.mark.asyncio
async def test_ingestion_llm_called_with_correct_role(mock_runtime):
    """Verify the LLM is called with AgentRole.PAPER_EXTRACTION."""
    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(),
    )

    with patch.object(ingestion, "_extract_pdf_text", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = "Test paper content."
        await ingestion.run(state, mock_runtime)

    # Check the mock LLM was called with the right role
    json_calls = [c for c in mock_runtime.llm.call_log if c["method"] == "generate_json"]
    assert len(json_calls) >= 1
    assert json_calls[0]["role"] == "paper_extraction"
    assert json_calls[0]["model_class"] == "PaperSummary"


def test_chunk_text_basic():
    """Test the chunking function directly."""
    text = " ".join(f"word{i}" for i in range(100))
    chunks = ingestion._chunk_text(text, chunk_size=30, overlap=5)
    assert len(chunks) >= 3
    # All chunks should have content
    assert all(len(chunk) > 0 for chunk in chunks)


def test_chunk_text_empty():
    """Empty text returns empty list."""
    assert ingestion._chunk_text("") == []


def test_chunk_text_short():
    """Short text returns single chunk."""
    chunks = ingestion._chunk_text("short text", chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == "short text"
