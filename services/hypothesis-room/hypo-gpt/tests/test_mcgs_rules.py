import numpy as np

from hypo_gpt.agents.generators import StrategyGenerator
from hypo_gpt.models import CausalChain, ExperimentSketch, GapAnalysis, HypothesisV2, IdeaTree, IdeaTreeNode, ResearchLandscape


def _mk_hyp(hid: str, strategy: str = "method_recomb") -> HypothesisV2:
    return HypothesisV2(
        hypo_id=hid,
        title=f"Hyp {hid}",
        strategy=strategy,
        problem_being_solved="deployment shift",
        core_claim="claim",
        causal_chain=CausalChain(
            intervention="intervene",
            intermediate="This is a sufficiently detailed intermediate mechanism with explicit causal mediator and measurable pathway described clearly.",
            outcome="outcome",
            conditions=["condition"],
            breaks_when=["break"],
        ),
        falsification_criterion="Disproved if metric is < 1.01x baseline under equal-compute condition.",
        grounding_paper_ids=["p1", "p2"],
        experiment=ExperimentSketch(
            design="design",
            baseline="baseline",
            primary_metric="metric",
            success_threshold=">=2%",
            compute_estimate="4xA100 for 18h",
            time_horizon="3_months",
            required_data="Public benchmark",
        ),
        composite_score=0.8,
    )


def test_recombine_only_when_similarity_low() -> None:
    tree = IdeaTree(research_query="test")
    n0 = IdeaTreeNode(node_id="n0", hypothesis=_mk_hyp("h0"), embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32).tolist())
    n1 = IdeaTreeNode(node_id="n1", hypothesis=_mk_hyp("h1"), embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32).tolist())
    tree.nodes = {"n0": n0, "n1": n1}

    generator = StrategyGenerator()
    # similarity is 1.0, so recombination must not choose multi-parent
    parent_ids = generator._select_parent_ids(tree, strategy="method_recomb")
    assert len(parent_ids) == 1

    tree.nodes["n1"].embedding = np.array([0.0, 1.0, 0.0], dtype=np.float32).tolist()
    parent_ids = generator._select_parent_ids(tree, strategy="method_recomb")
    assert 1 <= len(parent_ids) <= 2


def test_compose_payload_filters_generic_seed_text() -> None:
    generator = StrategyGenerator()
    gap = GapAnalysis(
        gap_type="method",
        statement="Transfer signal processing principles to cv pruning under deployment shift",
        why_it_matters="robustness under shift is weak",
        expected_impact="high",
        source_papers=["p1", "p2"],
    )
    landscape = ResearchLandscape(
        research_intent="Paper: ViNNPruner | Domain: cv",
        intent_domain="cv",
        methodological_consensus=["structured pruning", "ablation"],
        open_problems=["Which pruning-mask mediator causes shift-robust gains?"],
        established_facts=["ViNNPruner: interactive pruning improves compression-accuracy tradeoff."],
    )
    base = {
        "title_seed": "Method Recombination for pruning masks",
        "condition": "when single methods plateau",
        "core_claim": "combine structured pruning and calibration constraints around mediator probes",
        "mechanism_bias": "measure mediators under ablation",
        "outcome": "shift robustness improves",
        "falsification": "Disproved if shifted metric is < 1.03x baseline.",
        "design": "equal-compute ablation matrix",
        "success_threshold": ">=3% shifted gain",
    }
    llm_payload = {
        "title_seed": "Cross-Domain Transfer: Transferable Control Theory controls for ml optimization",
        "condition": "under generic regime",
        "core_claim": "improves performance and robustness",
        "mechanism_bias": "unknown mechanism",
        "outcome": "better performance",
        "falsification": "might fail",
        "design": "test variants",
        "success_threshold": "improve",
    }
    payload = generator._compose_payload(
        strategy="method_recomb",
        gap=gap,
        landscape=landscape,
        topic="ViNNPruner",
        base_payload=base,
        llm_payload=llm_payload,
    )
    assert "control theory techniques are underused in nlp training loops" not in payload["title_seed"].lower()
    assert "improves performance and robustness" not in payload["core_claim"].lower()
    assert "ablation" in payload["design"].lower()
    assert "compute" in payload["design"].lower()
    assert any(ch.isdigit() for ch in payload["falsification"])
