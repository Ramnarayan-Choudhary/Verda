from hypo_gpt.layer5_portfolio.constructor import fill_portfolio
from hypo_gpt.layer6_memory.memory_agent import MemoryAgentFacade
from hypo_gpt.layer6_memory.memory_store import InMemoryMemoryStore, make_memory_entry
from hypo_gpt.models import CausalChain, ExperimentSketch, HypothesisV2, JudgeScore, MemoryEntry, PanelVerdict


def _mk_hyp(hid: str, strategy: str, *, title: str | None = None) -> HypothesisV2:
    return HypothesisV2(
        hypo_id=hid,
        title=title or f"Hypothesis {hid}",
        strategy=strategy,
        problem_being_solved="deployment shift",
        core_claim="Intervention improves robustness.",
        causal_chain=CausalChain(
            intervention="apply intervention",
            intermediate="This is a long enough mechanistic pathway that explicitly describes mediator behavior and causal transmission to outcomes.",
            outcome="robustness improves",
            conditions=["deployment split"],
            breaks_when=["ablation removes effect"],
        ),
        falsification_criterion="Disproved if metric is < 1.01x baseline under equal-compute condition.",
        grounding_paper_ids=["p1", "p2"],
        experiment=ExperimentSketch(
            design="ablation ladder",
            baseline="equal compute baseline",
            primary_metric="metric",
            success_threshold=">=2%",
            compute_estimate="4xA100 for 18h",
            time_horizon="3_months",
            required_data="Public benchmark",
        ),
        novelty=0.8,
        feasibility=0.8,
        mechanism_coherence=0.8,
        executability=0.8,
        composite_score=0.8,
    )


def _mk_verdict(hid: str, score: float, novelty: float, feasibility: float, coherence: float, importance: float) -> PanelVerdict:
    judge = JudgeScore(
        judge_id="generalist",
        novelty=novelty,
        feasibility=feasibility,
        mechanism_coherence=coherence,
        executability=score,
        strategic_importance=importance,
        reasoning={},
    )
    return PanelVerdict(
        hypo_id=hid,
        scores=[judge],
        novelty_mean=novelty,
        novelty_var=0.0,
        feasibility_mean=feasibility,
        feasibility_var=0.0,
        coherence_mean=coherence,
        coherence_var=0.0,
        executability_mean=score,
        executability_var=0.0,
        importance_mean=importance,
        importance_var=0.0,
        controversy_score=0.0,
        panel_composite=score,
    )


def test_layer6_memory_store_roundtrip() -> None:
    store = InMemoryMemoryStore()
    agent = MemoryAgentFacade(backend=store)

    entry = make_memory_entry(
        session_id="s1",
        hypothesis_title="Failed direction",
        hypothesis_text="A failed hypothesis text",
        strategy="gap_fill",
        composite_score=0.2,
        panel_composite=0.2,
        metric_delta=-0.1,
        failure_reason="low score",
        domain_tags=["nlp"],
    )
    store.store_entries([entry])

    context, negatives, positives = agent.retrieve_context("failed hypothesis text", ["nlp"])
    assert len(negatives) >= 1
    assert len(positives) == 0
    assert "NEVER re-propose" in context


def test_layer5_fill_portfolio_selects_candidates() -> None:
    hypotheses = {
        "h1": _mk_hyp("h1", "gap_fill"),
        "h2": _mk_hyp("h2", "cross_domain"),
        "h3": _mk_hyp("h3", "assumption_challenge"),
        "h4": _mk_hyp("h4", "method_recomb"),
    }
    verdicts = [
        _mk_verdict("h1", 0.82, 0.75, 0.84, 0.8, 0.4),
        _mk_verdict("h2", 0.88, 0.86, 0.62, 0.78, 0.72),
        _mk_verdict("h3", 0.79, 0.70, 0.82, 0.75, 0.35),
        _mk_verdict("h4", 0.91, 0.90, 0.60, 0.80, 0.74),
    ]

    selected = fill_portfolio(verdicts, hypotheses, memory_negatives=[])
    assert 3 <= len(selected) <= 5
    assert all(item.hypo_id in hypotheses for item in selected)


def test_layer5_fill_portfolio_avoids_duplicate_titles() -> None:
    hypotheses = {
        "h1": _mk_hyp("h1", "method_recomb", title="Method Recombination for causal component interactions"),
        "h2": _mk_hyp("h2", "method_recomb", title="Method Recombination for causal component interactions"),
        "h3": _mk_hyp("h3", "cross_domain", title="Cross-domain Mechanism Transfer for ViNNPruner"),
        "h4": _mk_hyp("h4", "assumption_challenge", title="Assumption Stress-Test for ViNNPruner"),
    }
    verdicts = [
        _mk_verdict("h1", 0.91, 0.89, 0.62, 0.83, 0.74),
        _mk_verdict("h2", 0.90, 0.88, 0.61, 0.82, 0.73),
        _mk_verdict("h3", 0.87, 0.86, 0.66, 0.79, 0.72),
        _mk_verdict("h4", 0.84, 0.72, 0.81, 0.77, 0.35),
    ]

    selected = fill_portfolio(verdicts, hypotheses, memory_negatives=[])
    selected_titles = [hypotheses[item.hypo_id].title for item in selected]
    assert len(selected_titles) == len(set(selected_titles))


def test_layer6_store_panel_outcomes_writes_negative_entries() -> None:
    store = InMemoryMemoryStore()
    agent = MemoryAgentFacade(backend=store)
    verdicts = [
        _mk_verdict("h1", 0.82, 0.75, 0.84, 0.8, 0.4),
        _mk_verdict("h2", 0.33, 0.30, 0.41, 0.39, 0.2),
    ]
    texts = {"h1": "h1 robust mechanism text", "h2": "h2 weak mechanism text"}
    strategies = {"h1": "gap_fill", "h2": "cross_domain"}

    entries = agent.store_panel_outcomes(
        session_id="s2",
        domain_tags=["nlp"],
        verdicts=verdicts,
        selected_hypo_ids={"h1"},
        hypothesis_text_by_id=texts,
        strategy_by_id=strategies,
    )

    assert len(entries) == 2
    negatives = store.retrieve_negatives("weak mechanism text", ["nlp"])
    assert any(entry.hypothesis_title.startswith("h2") for entry in negatives)


def test_layer6_domain_filter_blocks_cross_domain_memory() -> None:
    store = InMemoryMemoryStore()
    entry = make_memory_entry(
        session_id="s3",
        hypothesis_title="Vision-only failure",
        hypothesis_text="vision model collapse under occlusion",
        strategy="failure_inversion",
        composite_score=0.2,
        panel_composite=0.2,
        metric_delta=-0.2,
        failure_reason="collapsed validation score",
        domain_tags=["computer_vision"],
    )
    store.store_entries([entry])

    negatives = store.retrieve_negatives("language model hallucination", ["nlp"])
    assert negatives == []
