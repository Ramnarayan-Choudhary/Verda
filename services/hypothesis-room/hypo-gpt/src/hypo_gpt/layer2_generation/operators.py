from __future__ import annotations

from typing import Optional

from hypo_gpt.models import HypothesisV2, ResearchSpaceMap

DEEPEN_PROMPT = "Add concrete mediator sub-steps to the causal chain intermediate."
NARROW_PROMPT = "Narrow scope to a testable regime within 3 months."
BROADEN_PROMPT = "Generalize claim while preserving causal mechanism."
INJECT_PROMPT = "Inject cross-domain bridge into mechanism reasoning."
CHALLENGE_PROMPT = "Challenge hidden assumption and derive new prediction."
RECOMBINE_PROMPT = "Recombine two hypotheses into one coherent mechanism."
SHARPEN_PROMPT = "Sharpen falsification criterion with numeric threshold."


def apply_operator(
    op: str,
    parent: HypothesisV2,
    space_map: ResearchSpaceMap,
    parent_b: Optional[HypothesisV2] = None,
) -> HypothesisV2:
    updated = parent.model_copy(deep=True)
    updated.mutation_operator = op

    if op == "deepen_mechanism":
        updated.causal_chain.intermediate = (
            f"{updated.causal_chain.intermediate} Explicit sub-step instrumentation and mediator readouts are added for causal traceability."
        )
    elif op == "narrow_scope":
        updated.problem_being_solved = f"{updated.problem_being_solved} Focused to a bounded 3-month evaluation regime."
        updated.experiment.time_horizon = "3_months"
    elif op == "broaden_claim":
        updated.core_claim = f"{updated.core_claim} This mechanism should generalize across related deployment regimes."
    elif op == "inject_analogy" and space_map.cross_domain_bridges:
        bridge = space_map.cross_domain_bridges[0]
        updated.source_domain_bridge = bridge.source_domain
        updated.causal_chain.intermediate = (
            f"{updated.causal_chain.intermediate} Analogized via {bridge.source_domain} -> {bridge.target_domain} transfer."
        )
    elif op == "challenge_assume" and space_map.contestable_assumptions:
        assumption = space_map.contestable_assumptions[0]
        updated.challenged_assumption = assumption.assumption
        updated.core_claim = f"{updated.core_claim} This explicitly relaxes assumption: {assumption.assumption}."
    elif op == "recombine" and parent_b is not None:
        updated.core_claim = f"{parent.core_claim} Combined with: {parent_b.core_claim}"
        updated.parent_hypo_ids = [parent.hypo_id, parent_b.hypo_id]
        updated.grounding_paper_ids = list({*parent.grounding_paper_ids, *parent_b.grounding_paper_ids})[:4]
    elif op == "sharpen_falsify":
        updated.falsification_criterion = "Hypothesis is disproved if primary_metric is < 1.01x baseline under equal-compute condition."

    return updated
