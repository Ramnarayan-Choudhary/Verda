from hypo_gpt.models import (
    GapAnalysis,
    MinimalTest,
    PaperIntelligence,
    PipelineConfig,
    StructuredHypothesis,
)


def test_models_validate_basic_objects() -> None:
    paper = PaperIntelligence(title="Test Paper", central_claim="claim")
    assert paper.title == "Test Paper"

    gap = GapAnalysis(
        gap_type="knowledge",
        statement="unknown",
        why_it_matters="important",
    )
    assert gap.gap_id.startswith("G")

    hypothesis = StructuredHypothesis(
        generation_strategy="assumption_challenger",
        source_gap_id=gap.gap_id,
        title="Test Hypothesis",
        condition="under shift",
        intervention="apply robust regularization",
        prediction="improves macro-F1",
        mechanism="regularization stabilizes gradients under shift",
        falsification_criterion="dead if metric unchanged",
        minimum_viable_test=MinimalTest(
            dataset="GLUE",
            baseline="baseline model",
            primary_metric="macro-F1",
            success_threshold=">5%",
            estimated_compute="1xA100",
            estimated_timeline="2 weeks",
        ),
        closest_existing_work="prior",
        novelty_claim="new coupling",
        expected_outcome_if_true="better robustness",
        expected_outcome_if_false="status quo",
        theoretical_basis="optimization",
    )
    assert hypothesis.id.startswith("hyp-")

    cfg = PipelineConfig(top_k=4)
    assert cfg.top_k == 4
