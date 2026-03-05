"""Shared test fixtures — mock LLM, mock runtime, mock external clients.

All integration tests use these fixtures to avoid real API calls.
The mock LLM returns deterministic JSON that passes Pydantic validation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import numpy as np
import pytest

from vreda_hypothesis.knowledge.graph import PaperKnowledgeGraph
from vreda_hypothesis.knowledge.vector_store import InMemoryVectorStore
from vreda_hypothesis.llm.provider import AgentRole
from vreda_hypothesis.models import (
    DimensionScores,
    EnhancedHypothesis,
    GapAnalysis,
    HypothesisSeed,
    HypothesisType,
    PaperMetadata,
    PaperSummary,
    PipelineConfig,
    PipelineState,
    ResearchGap,
    ScoredSeed,
    TokenUsage,
)


# ──────────────────────────────────────────────
# Deterministic mock responses per Pydantic model
# ──────────────────────────────────────────────

MOCK_PAPER_SUMMARY = {
    "title": "Attention Is All You Need",
    "authors": ["Vaswani et al."],
    "abstract": "We propose a new network architecture, the Transformer, based on attention mechanisms.",
    "methods": ["self-attention", "multi-head attention", "positional encoding"],
    "results": ["BLEU 28.4 on EN-DE", "BLEU 41.0 on EN-FR"],
    "limitations": ["quadratic memory in sequence length", "no inherent recurrence bias"],
    "datasets": ["WMT 2014 EN-DE", "WMT 2014 EN-FR"],
    "code_references": ["https://github.com/tensorflow/tensor2tensor"],
    "domain": "nlp",
    "key_equations": ["Attention(Q,K,V) = softmax(QK^T/sqrt(d_k))V"],
    "model_architecture": "encoder-decoder transformer",
    "contributions": ["self-attention replaces recurrence", "parallelizable training"],
}

MOCK_GAP_ANALYSIS = {
    "gaps": [
        {
            "id": "gap-test001",
            "gap_type": "unexplored_direction",
            "title": "Sparse attention for long sequences",
            "description": "Full attention is O(n^2); sparse patterns could enable 100k+ context.",
            "evidence": ["Longformer shows linear attention works"],
            "related_paper_titles": ["Longformer", "BigBird"],
            "potential_impact": "significant",
            "confidence": 75,
        },
        {
            "id": "gap-test002",
            "gap_type": "missing_evaluation",
            "title": "Transformer efficiency on low-resource languages",
            "description": "Most benchmarks focus on EN; low-resource settings are underexplored.",
            "evidence": [],
            "related_paper_titles": [],
            "potential_impact": "moderate",
            "confidence": 60,
        },
    ],
    "landscape_summary": "Transformer architectures dominate NLP but face scalability challenges.",
    "dominant_trends": ["scaling", "efficiency", "multimodal"],
    "underexplored_areas": ["sparse attention", "low-resource transfer"],
}

MOCK_SEED_BATCH = {
    "seeds": [
        {
            "text": "Replace full self-attention with learnable sparse patterns that adapt per-layer.",
            "type": "architecture_ablation",
            "predicted_impact": "10-30% memory reduction with <1% quality loss",
        },
        {
            "text": "Apply curriculum learning to transformer pre-training by ordering data by complexity.",
            "type": "efficiency_optimization",
            "predicted_impact": "Faster convergence, 20% fewer training tokens needed",
        },
        {
            "text": "Cross-domain transfer: use NLP transformer attention for protein folding contact maps.",
            "type": "cross_domain_transfer",
            "predicted_impact": "Novel application of attention to structural biology",
        },
    ]
}

MOCK_VERIFIABILITY = {"verifiability": 7, "notes": "Testable with standard NLP benchmarks"}

MOCK_HYPOTHESIS_DRAFT = {
    "title": "Adaptive Sparse Attention for Long-Context Transformers",
    "short_hypothesis": "Learnable per-layer sparsity patterns can replace full attention with minimal quality loss.",
    "description": "We hypothesize that attention heads develop distinct sparsity preferences during training.",
    "testable_prediction": "Sparse model achieves >98% of full attention BLEU with 50% less memory.",
    "expected_outcome": "A drop-in sparse attention module that enables 100k token contexts.",
    "required_modifications": ["Replace attention layers", "Add sparsity loss term"],
    "experiment_steps": ["Implement sparse attention", "Benchmark on WMT", "Profile memory usage"],
    "datasets": ["WMT 2014 EN-DE"],
    "metrics": ["BLEU", "memory usage", "inference latency"],
    "risk_factors": ["May hurt rare token attention patterns"],
    "grounding_evidence": ["Longformer shows linear attention feasibility"],
    "predicted_impact": "Significant memory savings enabling longer contexts",
    "novelty_angle": "Per-layer learned sparsity (not fixed patterns like Longformer)",
    "verifiability_score": 8,
    "type": "architecture_ablation",
    "novelty_score": 78,
    "feasibility_score": 72,
    "impact_score": 80,
    "grounding_score": 70,
    "testability_score": 85,
    "clarity_score": 82,
}

MOCK_CRITIC_OUTPUT = {
    "feasibility_issues": ["Requires custom CUDA kernels for efficient sparse ops"],
    "grounding_score": 0.75,
    "overlap_with_literature": "Partial overlap with Longformer/BigBird sparse patterns",
    "suggested_improvements": ["Compare against FlashAttention v2", "Test on code generation tasks"],
    "verdict": "viable",
    "revised_scores": {
        "novelty": 75, "feasibility": 68, "impact": 78,
        "grounding": 72, "testability": 82, "clarity": 80,
    },
}

MOCK_EVOLUTION_BATCH = {
    "ideas": [
        {
            "seed_text": "Combine sparse attention with mixture-of-experts routing for adaptive compute.",
            "type": "combination",
            "rationale": "MoE + sparsity could compound efficiency gains",
            "inherited_ids": ["hyp-test001"],
        }
    ]
}

MOCK_META_REVIEW = {
    "directives": ["Increase focus on efficiency metrics", "Need more cross-domain hypotheses"],
    "risk_alerts": ["Over-reliance on NLP benchmarks"],
}

MOCK_TOURNAMENT_DECISION = {
    "winner": "a",
    "rationale": "Hypothesis A is more novel and has clearer experimental design.",
    "novelty_winner": "a",
    "excitement_winner": "a",
    "feasibility_winner": "b",
    "impact_winner": "a",
}


# ──────────────────────────────────────────────
# Response routing — maps model class name to mock response
# ──────────────────────────────────────────────

_MOCK_RESPONSES: dict[str, dict] = {
    "PaperSummary": MOCK_PAPER_SUMMARY,
    "GapAnalysis": MOCK_GAP_ANALYSIS,
    "SeedBatch": MOCK_SEED_BATCH,
    "VerifiabilityPayload": MOCK_VERIFIABILITY,
    "QuickVerify": MOCK_VERIFIABILITY,
    "HypothesisDraft": MOCK_HYPOTHESIS_DRAFT,
    "CriticLLMOutput": MOCK_CRITIC_OUTPUT,
    "EvolutionBatch": MOCK_EVOLUTION_BATCH,
    "MetaReviewPayload": MOCK_META_REVIEW,
    "TournamentDecision": MOCK_TOURNAMENT_DECISION,
}


class MockLLMProvider:
    """Deterministic LLM mock — routes by Pydantic model class name."""

    def __init__(self) -> None:
        self.token_usage = TokenUsage()
        self.call_log: list[dict[str, Any]] = []

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        role: AgentRole = AgentRole.DEFAULT,
    ) -> str:
        self.call_log.append({"method": "generate", "role": role.value, "system_len": len(system)})
        return json.dumps(MOCK_PAPER_SUMMARY)

    async def generate_json(
        self,
        system: str,
        user: str,
        model_class: type,
        temperature: float = 0.2,
        role: AgentRole = AgentRole.DEFAULT,
        max_retries: int = 2,
    ):
        self.call_log.append({
            "method": "generate_json",
            "model_class": model_class.__name__,
            "role": role.value,
        })
        response_data = _MOCK_RESPONSES.get(model_class.__name__, {})
        return model_class.model_validate(response_data)

    async def generate_batch(
        self,
        prompts: list[tuple[str, str]],
        temperature: float = 0.5,
        role: AgentRole = AgentRole.DEFAULT,
        max_concurrent: int = 10,
    ) -> list[str]:
        return [json.dumps(MOCK_PAPER_SUMMARY)] * len(prompts)

    def get_active_providers(self) -> dict[str, str]:
        return {"default": "MockLLM (test)"}


class MockVectorStore:
    """In-memory vector store that skips embedding model loading."""

    def __init__(self) -> None:
        self._chunks: list[dict[str, Any]] = []

    async def add_chunks(self, doc_id: str, chunks: list[str]) -> None:
        for idx, text in enumerate(chunks):
            self._chunks.append({
                "id": f"{doc_id}:{idx}",
                "doc_id": doc_id,
                "text": text,
                "score": 0.5,
            })

    async def similarity_search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        # Return first k chunks with mock scores
        results = []
        for chunk in self._chunks[:k]:
            results.append({**chunk, "score": 0.5})
        if not results:
            results.append({"text": "mock context chunk", "score": 0.3})
        return results


class MockArxivClient:
    """Mock arXiv client returning deterministic metadata + a temp PDF path."""

    async def fetch_metadata(self, arxiv_id: str) -> PaperMetadata:
        return PaperMetadata(
            title="Attention Is All You Need",
            arxiv_id=arxiv_id,
            semantic_scholar_id="s2-12345",
            authors=["Vaswani", "Shazeer", "Parmar"],
            abstract="We propose a new network architecture, the Transformer.",
            year=2017,
            citation_count=90000,
            venue="NeurIPS 2017",
            url=f"https://arxiv.org/abs/{arxiv_id}",
        )

    async def download_pdf(self, arxiv_id: str) -> Path:
        """Create a minimal valid PDF file for testing."""
        tmp = Path("/tmp/test_paper.pdf")
        if not tmp.exists():
            # Minimal valid PDF
            tmp.write_bytes(
                b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
                b"/Contents 4 0 R>>endobj\n"
                b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td "
                b"(Test Paper) Tj ET\nendstream\nendobj\n"
                b"xref\n0 5\n0000000000 65535 f \n"
                b"0000000009 00000 n \n0000000058 00000 n \n"
                b"0000000115 00000 n \n0000000206 00000 n \n"
                b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n300\n%%EOF\n"
            )
        return tmp

    async def close(self) -> None:
        pass


class MockSemanticScholarClient:
    """Mock Semantic Scholar returning related papers."""

    async def fetch_paper(self, arxiv_id: str) -> PaperMetadata | None:
        return PaperMetadata(
            title="Attention Is All You Need",
            arxiv_id=arxiv_id,
            semantic_scholar_id="s2-12345",
            authors=["Vaswani"],
            abstract="Transformer architecture.",
            year=2017,
            citation_count=90000,
        )

    async def fetch_related(self, arxiv_id: str, limit: int = 30) -> list[PaperMetadata]:
        return [
            PaperMetadata(
                title="BERT: Pre-training of Deep Bidirectional Transformers",
                arxiv_id="1810.04805",
                authors=["Devlin", "Chang"],
                abstract="We introduce BERT, a language representation model.",
                year=2018,
                citation_count=70000,
            ),
            PaperMetadata(
                title="Longformer: The Long-Document Transformer",
                arxiv_id="2004.05150",
                authors=["Beltagy"],
                abstract="Sparse attention mechanism for long documents.",
                year=2020,
                citation_count=5000,
            ),
        ]

    async def keyword_search(self, query: str, limit: int = 5) -> list[PaperMetadata]:
        return []

    async def close(self) -> None:
        pass


class MockPapersWithCodeClient:
    """Mock PapersWithCode returning datasets and repos."""

    async def fetch_datasets(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return [
            {"name": "WMT 2014", "description": "English-German translation benchmark", "papers": [], "url": ""},
        ]

    async def fetch_repositories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return [
            {"name": "tensor2tensor", "framework": "tensorflow", "stars": 15000, "url": "https://github.com/tensorflow/tensor2tensor"},
        ]

    async def close(self) -> None:
        pass


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider()


@pytest.fixture
def mock_vector_store() -> MockVectorStore:
    return MockVectorStore()


@pytest.fixture
def mock_arxiv() -> MockArxivClient:
    return MockArxivClient()


@pytest.fixture
def mock_semantic_scholar() -> MockSemanticScholarClient:
    return MockSemanticScholarClient()


@pytest.fixture
def mock_paperswithcode() -> MockPapersWithCodeClient:
    return MockPapersWithCodeClient()


@pytest.fixture
def mock_runtime(mock_llm, mock_vector_store, mock_arxiv, mock_semantic_scholar, mock_paperswithcode):
    """Full PipelineRuntime with all mocked dependencies."""

    @dataclass
    class _MockRuntime:
        llm: Any
        arxiv: Any
        semantic_scholar: Any
        paperswithcode: Any
        vector_store: Any

    return _MockRuntime(
        llm=mock_llm,
        arxiv=mock_arxiv,
        semantic_scholar=mock_semantic_scholar,
        paperswithcode=mock_paperswithcode,
        vector_store=mock_vector_store,
    )


@pytest.fixture
def sample_paper_metadata() -> PaperMetadata:
    return PaperMetadata(
        title="Attention Is All You Need",
        arxiv_id="1706.03762",
        semantic_scholar_id="s2-12345",
        authors=["Vaswani", "Shazeer", "Parmar"],
        abstract="We propose a new network architecture, the Transformer, based on attention mechanisms.",
        year=2017,
        citation_count=90000,
        venue="NeurIPS 2017",
    )


@pytest.fixture
def sample_paper_summary() -> PaperSummary:
    return PaperSummary(**MOCK_PAPER_SUMMARY)


@pytest.fixture
def sample_gap_analysis() -> GapAnalysis:
    return GapAnalysis(**MOCK_GAP_ANALYSIS)


@pytest.fixture
def sample_seeds() -> list[HypothesisSeed]:
    return [
        HypothesisSeed(
            id=f"seed-test{i:03d}",
            text=text,
            type=HypothesisType.ARCHITECTURE_ABLATION,
            source_prompt="test",
        )
        for i, text in enumerate([
            "Replace full self-attention with learnable sparse patterns.",
            "Apply curriculum learning to transformer pre-training.",
            "Cross-domain transfer: use NLP attention for protein folding.",
            "Combine MoE routing with sparse attention heads.",
            "Use knowledge distillation to compress large transformers.",
        ])
    ]


@pytest.fixture
def sample_scored_seeds(sample_seeds) -> list[ScoredSeed]:
    return [
        ScoredSeed(
            seed=seed,
            novelty_score=0.7 + i * 0.05,
            budget_estimate_usd=2.0 + i * 0.5,
            verifiability_score=0.8,
            combined_score=0.7 + i * 0.03,
        )
        for i, seed in enumerate(sample_seeds)
    ]


@pytest.fixture
def sample_hypotheses() -> list[EnhancedHypothesis]:
    return [
        EnhancedHypothesis(
            id=f"hyp-test{i:03d}",
            type=HypothesisType.ARCHITECTURE_ABLATION,
            title=f"Test Hypothesis {i}",
            description=f"Description for hypothesis {i}",
            short_hypothesis=f"Short hypothesis {i}",
            testable_prediction=f"Prediction {i}",
            expected_outcome=f"Outcome {i}",
            scores=DimensionScores(
                novelty=70 + i * 3,
                feasibility=65 + i * 2,
                impact=75 + i,
                grounding=60 + i * 2,
                testability=80,
                clarity=78,
            ),
            composite_score=72 + i * 2,
            elo_rating=1500.0 + i * 20,
            reflection_rounds_completed=1,
        )
        for i in range(4)
    ]


@pytest.fixture
def sample_pipeline_state(
    sample_paper_metadata,
    sample_paper_summary,
    sample_gap_analysis,
    sample_seeds,
    sample_scored_seeds,
    sample_hypotheses,
    mock_vector_store,
) -> PipelineState:
    """A fully-populated pipeline state for testing later stages."""
    kg = PaperKnowledgeGraph()
    kg.add_paper(sample_paper_metadata, summary=sample_paper_summary, source="primary")

    return PipelineState(
        arxiv_id="1706.03762",
        config=PipelineConfig(max_seeds=20, max_cycles=2, top_k=3, tournament_rounds=2),
        paper_metadata=sample_paper_metadata,
        paper_summary=sample_paper_summary,
        paper_text="We propose a new network architecture based on attention mechanisms.",
        text_chunks=["chunk1: attention mechanism", "chunk2: encoder-decoder architecture"],
        related_papers=[
            PaperMetadata(title="BERT", arxiv_id="1810.04805", year=2018, citation_count=70000),
        ],
        gap_analysis=sample_gap_analysis,
        seeds=sample_seeds,
        filtered_seeds=sample_scored_seeds,
        refined_hypotheses=sample_hypotheses,
        elo_ratings={f"hyp-test{i:03d}": 1500.0 + i * 20 for i in range(4)},
        refinement_cycle=2,
        knowledge_graph=kg,
        vector_store_client=mock_vector_store,
    )
