"""Integration tests for Stage 2 — External Grounding & Gap Analysis."""

from __future__ import annotations

import pytest

from vreda_hypothesis.knowledge.graph import PaperKnowledgeGraph
from vreda_hypothesis.models import (
    GapAnalysis,
    MetaGap,
    PaperMetadata,
    PipelineConfig,
    PipelineState,
    PaperSummary,
)


@pytest.mark.asyncio
async def test_grounding_fetches_related_and_gaps(mock_runtime, sample_paper_metadata, sample_paper_summary, mock_vector_store):
    """Full grounding: fetch related papers + datasets + repos → gap analysis."""
    from vreda_hypothesis.stages import grounding

    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, summary=sample_paper_summary, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(),
        paper_metadata=sample_paper_metadata,
        paper_summary=sample_paper_summary,
        paper_text="We propose a new network architecture, the Transformer.",
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    result = await grounding.run(state, mock_runtime)

    assert "related_papers" in result
    assert "gap_analysis" in result
    assert "knowledge_graph" in result

    # Related papers fetched from mock Semantic Scholar
    related = result["related_papers"]
    assert len(related) >= 1
    assert all(isinstance(p, PaperMetadata) for p in related)

    # Gap analysis parsed correctly
    gap = result["gap_analysis"]
    assert isinstance(gap, GapAnalysis)
    assert len(gap.gaps) >= 1
    assert gap.gaps[0].gap_type in {"unexplored_direction", "missing_evaluation", "contradictory_findings", "scalability_question", "cross_domain_opportunity"}

    # Knowledge graph enriched with related papers
    graph = result["knowledge_graph"]
    assert graph.graph.number_of_nodes() >= 2  # primary + at least 1 related


@pytest.mark.asyncio
async def test_grounding_skips_without_metadata(mock_runtime):
    """Should return empty dict when paper_metadata is missing."""
    from vreda_hypothesis.stages import grounding

    state = PipelineState(config=PipelineConfig())
    result = await grounding.run(state, mock_runtime)
    assert result == {}


@pytest.mark.asyncio
async def test_grounding_handles_api_failures(mock_runtime, sample_paper_metadata, sample_paper_summary, mock_vector_store):
    """Should handle Semantic Scholar/PapersWithCode failures gracefully."""
    from vreda_hypothesis.stages import grounding

    # Make semantic scholar raise an exception
    async def _failing_fetch(*a, **kw):
        raise ConnectionError("API down")
    mock_runtime.semantic_scholar.fetch_related = _failing_fetch

    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(),
        paper_metadata=sample_paper_metadata,
        paper_summary=sample_paper_summary,
        paper_text="Test content.",
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    # Should not crash — handles exceptions via asyncio.gather(return_exceptions=True)
    result = await grounding.run(state, mock_runtime)
    # Gap analysis should still be produced (from whatever data is available)
    assert "gap_analysis" in result


@pytest.mark.asyncio
async def test_grounding_llm_called_with_gap_analysis_role(mock_runtime, sample_paper_metadata, sample_paper_summary, mock_vector_store):
    """Verify gap analysis uses AgentRole.GAP_ANALYSIS."""
    from vreda_hypothesis.stages import grounding

    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, source="primary")

    state = PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(),
        paper_metadata=sample_paper_metadata,
        paper_summary=sample_paper_summary,
        paper_text="Test content.",
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    await grounding.run(state, mock_runtime)

    json_calls = [c for c in mock_runtime.llm.call_log if c["method"] == "generate_json"]
    assert any(c["role"] == "gap_analysis" for c in json_calls)
    assert any(c["model_class"] == "GapAnalysis" for c in json_calls)


@pytest.mark.asyncio
async def test_grounding_generates_meta_gap_fallback_when_llm_fails(
    mock_runtime, sample_paper_metadata, sample_paper_summary, mock_vector_store
):
    """When gap synthesis LLM paths fail, stage should still emit structured heuristic meta-gaps."""
    from vreda_hypothesis.stages import grounding

    async def _empty_related(*a, **kw):
        return []

    async def _always_fail(*a, **kw):
        raise RuntimeError("forced-llm-failure")

    mock_runtime.semantic_scholar.fetch_related = _empty_related
    mock_runtime.semantic_scholar.keyword_search = _empty_related
    mock_runtime.llm.generate_json = _always_fail

    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, summary=sample_paper_summary, source="primary")
    state = PipelineState(
        arxiv_id=None,
        config=PipelineConfig(),
        paper_metadata=sample_paper_metadata,
        paper_summary=sample_paper_summary,
        paper_text="Transformer-style method with sparse operators and limitations under shift.",
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )

    result = await grounding.run(state, mock_runtime)
    assert "meta_gaps" in result
    assert len(result["meta_gaps"]) >= 1
    assert all(isinstance(g, MetaGap) for g in result["meta_gaps"])


@pytest.mark.asyncio
async def test_web_literature_search_uses_openai_client_when_available(
    mock_runtime,
    sample_paper_summary,
) -> None:
    """Web grounding should support OpenAI web-search results."""
    from vreda_hypothesis.stages import grounding

    class _MockOpenAIWebSearch:
        is_configured = True

        async def search(self, query: str, max_results: int = 3, allowed_domains=None):
            return [
                {
                    "title": "Sparse Attention Survey",
                    "content": "Compares sparse transformers and long-context scaling.",
                    "url": "https://arxiv.org/abs/2401.12345",
                }
            ]

    mock_runtime.tavily = None
    mock_runtime.openai_web_search = _MockOpenAIWebSearch()

    state = PipelineState(
        config=PipelineConfig(),
        paper_summary=sample_paper_summary,
        paper_metadata=PaperMetadata(title=sample_paper_summary.title),
        paper_text="placeholder",
    )
    snippets = await grounding._web_literature_search(
        state,
        mock_runtime,
        seen_titles=set(),
    )

    assert snippets
    assert any("Web/openai_web_search" in snippet for snippet in snippets)
