from hypo_gpt.agents.external_grounding import ExternalGrounder, _extract_title_from_intent, _looks_like_temp_title


def test_extract_title_from_intent_prefers_real_paper_title() -> None:
    intent = (
        "Paper: ViNNPruner: Visual Interactive Pruning for Deep Learning | "
        "Domain: cv | Objective: produce grounded hypotheses"
    )
    title = _extract_title_from_intent(intent)
    assert title == "ViNNPruner: Visual Interactive Pruning for Deep Learning"


def test_build_queries_filters_temp_artifact_tokens() -> None:
    intent = (
        "Paper: vreda_hyp_3f66f168-8082-490f-9d1f-e48d86f89a60_ba0fb6fb | "
        "Domain: cv | Objective: identify pruning ablation benchmark opportunities"
    )
    queries = ExternalGrounder._build_queries(
        primary_title="uploaded research paper",
        research_intent=intent,
        domain="cv",
    )
    assert len(queries) >= 3
    assert all("vreda_hyp_" not in query.lower() for query in queries)
    assert _looks_like_temp_title("vreda_hyp_3f66f168-8082-490f-9d1f-e48d86f89a60")
