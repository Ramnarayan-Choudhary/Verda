from hypo_gpt.layer2_generation.strategies import STRATEGY_BUILDERS
from hypo_gpt.models import GapAnalysis


def test_all_strategy_builders_emit_required_contract_fields() -> None:
    gap = GapAnalysis(
        gap_type="knowledge",
        statement="robustness under deployment shift remains weakly explained",
        why_it_matters="deployment reliability is limited",
        expected_impact="high",
        nearest_prior_work="benchmark-focused studies",
        source_papers=["p1", "p2"],
    )
    required = {
        "title_seed",
        "condition",
        "core_claim",
        "mechanism_bias",
        "outcome",
        "falsification",
        "design",
        "success_threshold",
    }

    assert len(STRATEGY_BUILDERS) == 7
    for name, builder in STRATEGY_BUILDERS.items():
        payload = builder(gap, round_index=0)
        assert required.issubset(payload.keys()), f"missing contract keys for strategy={name}"
