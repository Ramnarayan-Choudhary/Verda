"""Unit tests for hypo-claude models — JSON round-trip, defaults, validators."""

import json

from hypo_claude.models import (
    DIMENSION_WEIGHTS,
    GENERATION_STRATEGIES,
    JUDGE_WEIGHTS,
    MUTATION_STRATEGIES,
    DimensionScores,
    DomainCritique,
    GapAnalysis,
    GenerateRequest,
    GeneratorOutput,
    JudgeScore,
    MinimalTest,
    PaperIntelligence,
    PipelineConfig,
    PipelineState,
    PortfolioHypothesis,
    ProgressEvent,
    ResearchLandscape,
    ResearchPortfolio,
    ResearchSpaceMap,
    ResourceSummary,
    StructuredHypothesis,
    TokenUsage,
    TribunalVerdict,
    compute_panel_composite,
)


class TestPaperIntelligence:
    def test_defaults(self):
        pi = PaperIntelligence()
        assert pi.title == ""
        assert pi.key_assumptions == []
        assert pi.confidence_level == "preliminary"

    def test_list_coercion(self):
        pi = PaperIntelligence(key_assumptions="single string")
        assert pi.key_assumptions == ["single string"]

    def test_round_trip(self):
        pi = PaperIntelligence(title="Test", domain="ML", central_claim="X works")
        data = json.loads(pi.model_dump_json())
        pi2 = PaperIntelligence.model_validate(data)
        assert pi2.title == "Test"
        assert pi2.domain == "ML"


class TestResearchSpaceMap:
    def test_all_gaps(self):
        rsm = ResearchSpaceMap(
            knowledge_gaps=[GapAnalysis(statement="gap1")],
            method_gaps=[GapAnalysis(statement="gap2")],
        )
        assert len(rsm.all_gaps) == 2

    def test_get_gap(self):
        g = GapAnalysis(gap_id="gap-test", statement="test")
        rsm = ResearchSpaceMap(knowledge_gaps=[g])
        assert rsm.get_gap("gap-test") is not None
        assert rsm.get_gap("nonexistent") is None


class TestStructuredHypothesis:
    def test_has_id(self):
        h = StructuredHypothesis(title="Test")
        assert h.id.startswith("hyp-")


class TestDimensionScores:
    def test_composite(self):
        ds = DimensionScores(
            mechanistic_quality=80, novelty=70, testability=60,
            impact=50, feasibility=90, specificity=40, creativity=30,
        )
        composite = ds.composite
        expected = (80 * 0.25 + 70 * 0.20 + 60 * 0.20 + 50 * 0.15 + 90 * 0.10 + 40 * 0.05 + 30 * 0.05)
        assert abs(composite - round(expected, 1)) < 0.1

    def test_weights_sum_to_one(self):
        assert abs(sum(DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9


class TestPanelComposite:
    def test_weighted_average(self):
        scores = [
            JudgeScore(judge_persona="conservative", scores=DimensionScores(mechanistic_quality=80)),
            JudgeScore(judge_persona="generalist", scores=DimensionScores(mechanistic_quality=60)),
            JudgeScore(judge_persona="practitioner", scores=DimensionScores(mechanistic_quality=70)),
        ]
        result = compute_panel_composite(scores)
        assert result > 0

    def test_empty(self):
        assert compute_panel_composite([]) == 0.0


class TestResearchPortfolio:
    def test_slot_properties(self):
        rp = ResearchPortfolio(hypotheses=[
            PortfolioHypothesis(portfolio_slot="safe"),
            PortfolioHypothesis(portfolio_slot="medium"),
            PortfolioHypothesis(portfolio_slot="moonshot"),
        ])
        assert len(rp.safe_hypotheses) == 1
        assert len(rp.medium_hypotheses) == 1
        assert len(rp.moonshot_hypotheses) == 1


class TestTokenUsage:
    def test_add(self):
        t = TokenUsage()
        t.add(100, 50, 0.01)
        assert t.prompt_tokens == 100
        assert t.total_tokens == 150
        assert t.estimated_cost_usd == 0.01


class TestPipelineConfig:
    def test_defaults(self):
        c = PipelineConfig()
        assert c.max_hypotheses_per_strategy == 5
        assert c.tribunal_cycles == 3

    def test_extra_ignored(self):
        c = PipelineConfig(unknown_field="ignored")
        assert not hasattr(c, "unknown_field")


class TestConstants:
    def test_seven_strategies(self):
        assert len(GENERATION_STRATEGIES) == 7

    def test_five_mutations(self):
        assert len(MUTATION_STRATEGIES) == 5

    def test_judge_weights_sum(self):
        assert abs(sum(JUDGE_WEIGHTS.values()) - 1.0) < 1e-9


class TestProgressEvent:
    def test_serialization(self):
        e = ProgressEvent(type="progress", step="intelligence", message="Working...", current=1, total=5)
        data = json.loads(e.model_dump_json())
        assert data["type"] == "progress"
        assert data["current"] == 1
