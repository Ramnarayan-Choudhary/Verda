from hypo_gpt.models import (
    CausalChain,
    ExperimentSketch,
    GapAnalysis,
    HypothesisV2,
    IdeaTree,
    IdeaTreeNode,
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

    cfg = PipelineConfig(top_k=4, domain_hint="cv")
    assert cfg.top_k == 4
    assert cfg.domain_hint == "cv"
    assert cfg.pipeline_version == "v2"
    assert cfg.output_schema == "legacy"
    assert cfg.max_rounds == 4
    assert cfg.enable_external_search is True


def test_hypothesis_v2_validation_rules() -> None:
    chain = CausalChain(
        intervention="Apply intervention X under matched compute budget.",
        intermediate="This intervention creates a measured mediator pathway that isolates confounders and propagates causal changes to the final robust performance metric.",
        outcome="Primary metric improves under shift.",
        conditions=["deployment-like split"],
        breaks_when=["ablation removes mediator effect"],
    )
    experiment = ExperimentSketch(
        design="Ablation ladder on public benchmark with repeated seeds.",
        baseline="Matched baseline under equal compute.",
        primary_metric="robustness-adjusted score",
        success_threshold=">=2% gain",
        compute_estimate="4xA100 for 18h",
        time_horizon="3_months",
        required_data="Public benchmark suite",
    )
    hyp = HypothesisV2(
        title="Test Hypothesis V2",
        strategy="gap_fill",
        problem_being_solved="deployment shift under resource constraints",
        core_claim="Intervention X improves robustness through mediator M.",
        causal_chain=chain,
        falsification_criterion="Disproved if metric is < 1.02x baseline under equal-compute condition.",
        grounding_paper_ids=["paper_a", "paper_b"],
        experiment=experiment,
    )
    assert hyp.strategy == "gap_fill"
