from hypo_gpt.layer4_panel.panel import evaluate_panel
from hypo_gpt.models import CausalChain, ExperimentSketch, HypothesisV2


def _hypothesis() -> HypothesisV2:
    return HypothesisV2(
        hypo_id="h-panel-1",
        title="Shift-Robust Mediator Control",
        strategy="cross_domain",
        problem_being_solved="robustness degradation under deployment shift",
        core_claim="Introduce mediator-constrained optimization to preserve robustness under shift.",
        causal_chain=CausalChain(
            intervention="apply mediator-constrained objective during training",
            intermediate=(
                "Mediator-constrained objectives reduce spurious feature reliance and preserve stable internal states "
                "across stress conditions, improving causal transfer to deployment outcomes."
            ),
            outcome="robustness-adjusted metric improves under deployment shift",
            conditions=["equal compute budget", "fixed data protocol"],
            breaks_when=["mediator ablation removes robustness gains"],
        ),
        falsification_criterion="Disproved if robustness metric is < 1.02x baseline under equal-compute stress evaluation.",
        grounding_paper_ids=["p1", "p2"],
        experiment=ExperimentSketch(
            design="controlled ablation ladder with stress-suite replication",
            baseline="equal-compute baseline with repeated seeds",
            primary_metric="robustness-adjusted metric",
            success_threshold=">=2% robust gain",
            compute_estimate="4xA100 for 18h",
            time_horizon="3_months",
            required_data="Public benchmark with shift splits",
        ),
        novelty=0.82,
        feasibility=0.74,
        mechanism_coherence=0.81,
        executability=0.77,
        composite_score=0.79,
    )


def test_layer4_panel_judges_disagree_and_fill_variance() -> None:
    verdict = evaluate_panel(_hypothesis(), risk_appetite="balanced", tribunal_bundle={"mechanism": {"is_logically_valid": True}})
    assert len(verdict.scores) == 3
    assert verdict.controversy_score > 0.0
    assert verdict.novelty_var > 0.0
    assert verdict.executability_var > 0.0


def test_layer4_panel_risk_appetite_changes_composite() -> None:
    hypothesis = _hypothesis()
    conservative = evaluate_panel(hypothesis, risk_appetite="conservative")
    moonshot = evaluate_panel(hypothesis, risk_appetite="moonshot")
    assert conservative.panel_composite != moonshot.panel_composite
