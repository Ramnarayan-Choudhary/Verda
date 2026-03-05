"""Integration tests for Stage 7 — Structured Output."""

from __future__ import annotations

import pytest

from vreda_hypothesis.models import (
    EnhancedHypothesis,
    HypothesisType,
    PaperSummary,
    GeneratorOutput,
    PipelineConfig,
    PipelineState,
)
from vreda_hypothesis.stages import output


def test_output_produces_generator_output(sample_hypotheses, sample_gap_analysis):
    """Full output stage: candidates → GeneratorOutput."""
    state = PipelineState(
        config=PipelineConfig(top_k=3),
        tournament_results=sample_hypotheses,
        gap_analysis=sample_gap_analysis,
        meta_review_notes=["boost novelty", "add cross-domain"],
        refinement_cycle=2,
    )

    result = output.run(state)

    assert "final_output" in result
    final = result["final_output"]
    assert isinstance(final, GeneratorOutput)
    assert len(final.hypotheses) == 3  # top_k=3
    assert final.gap_analysis_used is True
    assert final.reflection_rounds == 2
    assert final.generation_strategy == "knowledge_grounded"
    assert "Gaps considered:" in final.reasoning_context
    assert "Elo span:" in final.reasoning_context


def test_output_falls_back_to_refined(sample_hypotheses):
    """When tournament_results is empty, should use refined_hypotheses."""
    state = PipelineState(
        config=PipelineConfig(top_k=2),
        refined_hypotheses=sample_hypotheses,
        refinement_cycle=1,
    )

    result = output.run(state)
    assert "final_output" in result
    assert len(result["final_output"].hypotheses) == 2


def test_output_resilient_when_no_ranked_candidates(sample_paper_summary):
    """Should synthesize fallback hypotheses when ranking stages produce no finalists."""
    state = PipelineState(
        config=PipelineConfig(top_k=4),
        paper_summary=sample_paper_summary,
        refinement_cycle=0,
    )
    result = output.run(state)
    assert "final_output" in result
    final = result["final_output"]
    assert len(final.hypotheses) == 4
    assert "Fallback synthesis used" in final.reasoning_context


def test_output_resilient_when_only_paper_text_available():
    """Should synthesize fallback hypotheses even when summary/seeds are unavailable."""
    state = PipelineState(
        config=PipelineConfig(top_k=3),
        paper_text=(
            "We propose a multi-regime sparse activation training strategy for residual networks. "
            "Our method improves test accuracy while reducing memory use by adapting keep-ratio schedules. "
            "We demonstrate robust gains across CIFAR-100 and ImageNet settings."
        ),
        refinement_cycle=0,
    )
    result = output.run(state)
    assert "final_output" in result
    final = result["final_output"]
    assert len(final.hypotheses) == 3
    assert all(h.title for h in final.hypotheses)
    assert "Fallback synthesis used" in final.reasoning_context
    assert len({h.type for h in final.hypotheses}) >= 2
    assert len({h.title for h in final.hypotheses}) == len(final.hypotheses)


def test_output_top_k_limits_results(sample_hypotheses):
    """Should respect top_k config."""
    state = PipelineState(
        config=PipelineConfig(top_k=1),
        tournament_results=sample_hypotheses,
        refinement_cycle=1,
    )
    result = output.run(state)
    assert len(result["final_output"].hypotheses) == 1


def test_output_serializes_to_frontend_format(sample_hypotheses):
    """Output should serialize to JSON compatible with HypothesisSelector.tsx."""
    state = PipelineState(
        config=PipelineConfig(top_k=3),
        tournament_results=sample_hypotheses,
        refinement_cycle=1,
    )
    result = output.run(state)
    final = result["final_output"]

    # Serialize to dict (mimics JSON.parse in frontend)
    data = final.model_dump()
    assert "hypotheses" in data
    assert "reasoning_context" in data
    assert "gap_analysis_used" in data
    assert "reflection_rounds" in data
    assert "generation_strategy" in data

    # Each hypothesis should have the expected fields
    for hyp in data["hypotheses"]:
        assert "id" in hyp
        assert "type" in hyp
        assert "title" in hyp
        assert "scores" in hyp
        assert "composite_score" in hyp
        assert "elo_rating" in hyp
        # Scores should be 6-dimensional
        scores = hyp["scores"]
        assert set(scores.keys()) == {"novelty", "feasibility", "impact", "grounding", "testability", "clarity"}


def test_output_includes_sota_payload(sample_hypotheses, sample_paper_summary):
    """Final output should include strict Stage-1 SOTA payload."""
    state = PipelineState(
        config=PipelineConfig(top_k=3),
        tournament_results=sample_hypotheses,
        paper_summary=sample_paper_summary,
        refinement_cycle=1,
    )
    result = output.run(state)
    final = result["final_output"]

    assert final.sota_payload is not None
    payload = final.sota_payload.model_dump()
    assert set(payload.keys()) == {"research_frame", "meta_gaps", "hypotheses", "portfolio_audit"}
    assert len(payload["hypotheses"]) >= 1
    for hyp in payload["hypotheses"]:
        assert "IF " in hyp["statement"] or "if " in hyp["statement"]
        assert len(hyp["mve"]) == 5
        assert hyp["experiment"]["dataset"]
        assert hyp["experiment"]["metric"]
        assert "Dead if" in hyp["experiment"]["falsification_threshold"] or "dead if" in hyp["experiment"]["falsification_threshold"]


def test_output_recovers_from_non_compliant_candidates() -> None:
    """Regression: strict gate must not produce zero-finalist output."""
    bad_candidate = EnhancedHypothesis(
        type=HypothesisType.ARCHITECTURE_ABLATION,
        title="Vague candidate",
        statement="Maybe this might help.",
        testable_prediction="could improve",
        expected_outcome="better results",
    )
    state = PipelineState(
        config=PipelineConfig(top_k=4),
        paper_summary=PaperSummary(domain="ml", datasets=[]),
        tournament_results=[bad_candidate],
    )

    result = output.run(state)
    final = result["final_output"]
    assert len(final.hypotheses) == 4
    for hypothesis in final.hypotheses:
        assert hypothesis.experiment_spec.dataset
        assert "dataset" not in hypothesis.experiment_spec.dataset.lower()
