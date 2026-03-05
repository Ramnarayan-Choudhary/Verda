"""Tests for Pydantic models — serialization, validation, and frontend compatibility."""

from __future__ import annotations

import json

from vreda_hypothesis.models import (
    DimensionScores,
    EnhancedHypothesis,
    GapAnalysis,
    GenerateRequest,
    GeneratorOutput,
    HypothesisSeed,
    HypothesisType,
    MetaGap,
    PaperSummary,
    PipelineConfig,
    PipelineState,
    ProgressEvent,
    ResearchGap,
    ScoredSeed,
    TokenUsage,
    compute_composite_score,
)


class TestDimensionScores:
    def test_defaults_to_zero(self):
        scores = DimensionScores()
        assert scores.novelty == 0
        assert scores.clarity == 0

    def test_enforces_range(self):
        scores = DimensionScores(novelty=100, feasibility=0)
        assert scores.novelty == 100
        assert scores.feasibility == 0

    def test_composite_score(self):
        scores = DimensionScores(novelty=80, feasibility=70, impact=90, grounding=60, testability=75, clarity=85)
        composite = compute_composite_score(scores)
        # Weighted: 80*0.25 + 70*0.20 + 90*0.20 + 60*0.15 + 75*0.10 + 85*0.10
        # = 20 + 14 + 18 + 9 + 7.5 + 8.5 = 77
        assert composite == 77

    def test_composite_all_zeros(self):
        assert compute_composite_score(DimensionScores()) == 0

    def test_composite_all_hundred(self):
        scores = DimensionScores(novelty=100, feasibility=100, impact=100, grounding=100, testability=100, clarity=100)
        assert compute_composite_score(scores) == 100


class TestEnhancedHypothesis:
    def test_serializes_to_json(self):
        hyp = EnhancedHypothesis(
            title="Test",
            type=HypothesisType.ARCHITECTURE_ABLATION,
            description="A test hypothesis",
            scores=DimensionScores(novelty=80, feasibility=70, impact=75, grounding=65, testability=80, clarity=78),
            composite_score=75,
            elo_rating=1520.0,
        )
        data = json.loads(hyp.model_dump_json())

        # Frontend expects these exact fields
        assert "id" in data
        assert data["type"] == "architecture_ablation"
        assert data["scores"]["novelty"] == 80
        assert data["elo_rating"] == 1520.0
        assert data["composite_score"] == 75

    def test_default_id_generated(self):
        hyp = EnhancedHypothesis()
        assert hyp.id.startswith("hyp-")

    def test_hypothesis_types(self):
        for ht in HypothesisType:
            hyp = EnhancedHypothesis(type=ht)
            assert hyp.type == ht


class TestGeneratorOutput:
    def test_serializes_for_frontend(self):
        output = GeneratorOutput(
            hypotheses=[
                EnhancedHypothesis(title="H1", composite_score=80),
                EnhancedHypothesis(title="H2", composite_score=70),
            ],
            reasoning_context="test context",
            gap_analysis_used=True,
            reflection_rounds=3,
        )
        data = output.model_dump()

        assert len(data["hypotheses"]) == 2
        assert data["generation_strategy"] == "knowledge_grounded"
        assert data["reflection_rounds"] == 3


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig()
        assert config.max_seeds == 200
        assert config.max_cycles == 4
        assert config.top_k == 10
        assert config.budget_limit_usd == 5.0

    def test_custom_values(self):
        config = PipelineConfig(max_seeds=50, max_cycles=2, top_k=5)
        assert config.max_seeds == 50

    def test_accepts_camel_case_keys(self):
        config = PipelineConfig.model_validate(
            {
                "maxSeeds": 32,
                "maxCycles": 3,
                "topK": 4,
                "groundingTimeoutSeconds": 240,
            }
        )
        assert config.max_seeds == 32
        assert config.max_cycles == 3
        assert config.top_k == 4
        assert config.stage_timeouts_seconds.get("grounding") == 240


class TestProgressEvent:
    def test_ndjson_format(self):
        event = ProgressEvent(type="progress", step="ingestion", message="Fetching paper", current=1, total=7)
        line = event.model_dump_json()
        parsed = json.loads(line)
        assert parsed["type"] == "progress"
        assert parsed["step"] == "ingestion"
        assert parsed["current"] == 1
        assert parsed["total"] == 7


class TestTokenUsage:
    def test_accumulates(self):
        usage = TokenUsage()
        usage.add(prompt=100, completion=50, cost=0.01)
        usage.add(prompt=200, completion=100, cost=0.02)
        assert usage.prompt_tokens == 300
        assert usage.completion_tokens == 150
        assert usage.total_tokens == 450
        assert abs(usage.estimated_cost_usd - 0.03) < 1e-9


class TestScoredSeed:
    def test_creation(self):
        seed = HypothesisSeed(text="test", type=HypothesisType.SCALE)
        scored = ScoredSeed(
            seed=seed,
            novelty_score=0.8,
            budget_estimate_usd=3.5,
            verifiability_score=0.7,
            combined_score=0.75,
        )
        assert scored.seed.text == "test"
        assert scored.combined_score == 0.75


class TestGenerateRequest:
    def test_with_arxiv_id(self):
        req = GenerateRequest(arxiv_id="1706.03762")
        assert req.arxiv_id == "1706.03762"
        assert req.pdf_path is None

    def test_with_config(self):
        req = GenerateRequest(
            arxiv_id="1706.03762",
            config=PipelineConfig(max_seeds=50),
        )
        assert req.config.max_seeds == 50


class TestResearchGap:
    def test_gap_types(self):
        for gap_type in ["unexplored_direction", "contradictory_findings", "missing_evaluation", "scalability_question", "cross_domain_opportunity"]:
            gap = ResearchGap(gap_type=gap_type, title="Test", description="Test gap", potential_impact="moderate")
            assert gap.gap_type == gap_type

    def test_default_id(self):
        gap = ResearchGap(gap_type="unexplored_direction", title="Test", description="Test", potential_impact="significant")
        assert gap.id.startswith("gap-")


class TestMetaGap:
    def test_accepts_legacy_gap_keys(self):
        gap = MetaGap.model_validate(
            {
                "id": "G1",
                "type": "empirical",
                "description": "No work tests X under Y on Z",
                "why": "Important for mechanism validity",
                "closest_paper": "Paper A",
                "iteration_history": "Round 1: initial",
            }
        )
        assert gap.gap_id == "G1"
        assert gap.gap_type == "empirical"
        assert gap.statement.startswith("No work tests")
        assert gap.iteration_history == ["Round 1: initial"]


class TestPaperSummary:
    def test_coerces_string_list_fields(self):
        summary = PaperSummary.model_validate(
            {
                "title": "T",
                "authors": "Alice",
                "methods": "LoRA, sparse attention",
            }
        )
        assert summary.authors == ["Alice"]
        assert summary.methods == ["LoRA", "sparse attention"]
