"""Layer 3 — Adversarial Tribunal with 3-Cycle Mutation Targeting.

For each hypothesis:
  Cycle 1: MECHANISM_DEEPENING — strengthen causal chains
  Cycle 2: FEASIBILITY_ANCHORING — address resource/executability issues
  Cycle 3: FALSIFICATION_SHARPENING — tighten predictions and falsification criteria

5 critics per hypothesis (parallel, isolated) + mechanism validator gate.
IdeaTree tracks lineage and backpropagates composite scores.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import structlog

from hypo_claude.agents.evolver import EvolverAgent
from hypo_claude.agents.tribunal import TribunalPanel
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import (
    IdeaTree,
    ResearchLandscape,
    StructuredHypothesis,
    TribunalVerdict,
)

logger = structlog.get_logger(__name__)

# 3-cycle mutation targeting: each cycle focuses on a specific weakness class
CYCLE_MUTATION_MAP = {
    0: {  # Cycle 1: Mechanism deepening
        "target": "mechanism",
        "mutation_key": "mechanism_deepening",
        "trigger": lambda v: (
            v.mechanism_validation.logical_score < 0.7
            or not v.mechanism_validation.is_logically_valid
            or v.devils_advocate.strongest_objection != ""
        ),
    },
    1: {  # Cycle 2: Feasibility anchoring
        "target": "feasibility",
        "mutation_key": "condition_specification",
        "trigger": lambda v: (
            v.resource_reality.feasibility_score < 0.5
            or not v.resource_reality.data_available
            or v.executability.exec_score < 0.5
        ),
    },
    2: {  # Cycle 3: Falsification sharpening
        "target": "falsification",
        "mutation_key": "prediction_sharpening",
        "trigger": lambda v: True,  # Always sharpen in final cycle
    },
}


def _compute_verdict_score(verdict: TribunalVerdict) -> float:
    """Compute a composite score from verdict for IdeaTree backpropagation."""
    return (
        verdict.domain_validity.domain_validity_score * 0.25
        + verdict.mechanism_validation.logical_score * 0.25
        + verdict.resource_reality.feasibility_score * 0.20
        + verdict.executability.exec_score * 0.15
        + (1.0 if not verdict.devils_advocate.strongest_objection else 0.5) * 0.15
    )


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 3: Iterative adversarial refinement with 3-cycle mutation targeting."""

    hypothesis_pool: list[StructuredHypothesis] = state["hypothesis_pool"]
    landscape: ResearchLandscape = state["research_landscape"]
    config = state.get("config")
    max_cycles = config.tribunal_cycles if config else 3
    max_cycles = min(max_cycles, 3)  # Cap at 3 for the 3-cycle targeting pattern
    max_concurrent = config.max_concurrent_critics if hasattr(config, "max_concurrent_critics") else 4

    # Fast mode when few hypotheses — 2 critics instead of 5 (saves ~60% of LLM calls)
    fast_mode = len(hypothesis_pool) <= 7
    panel = TribunalPanel(llm, fast_mode=fast_mode)
    evolver = EvolverAgent(llm)

    # Initialize IdeaTree from the hypothesis pool
    idea_tree = state.get("idea_tree") or IdeaTree()
    hyp_to_node: dict[str, str] = {}  # hypothesis_id -> node_id
    for h in hypothesis_pool:
        node = idea_tree.add_node(h)
        hyp_to_node[h.id] = node.node_id

    current_pool = list(hypothesis_pool)
    all_verdicts: dict[str, TribunalVerdict] = {}
    advanced_total: list[StructuredHypothesis] = []

    for cycle in range(max_cycles):
        if not current_pool:
            break

        cycle_config = CYCLE_MUTATION_MAP.get(cycle, CYCLE_MUTATION_MAP[2])

        if progress:
            await progress(
                "tribunal",
                f"Tribunal cycle {cycle + 1}/{max_cycles} ({cycle_config['target']}) — "
                f"evaluating {len(current_pool)} hypotheses",
                cycle, max_cycles,
            )

        # Evaluate all hypotheses in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _evaluate(
            h: StructuredHypothesis,
        ) -> tuple[StructuredHypothesis, TribunalVerdict | None, Exception | None]:
            async with semaphore:
                try:
                    verdict = await panel.evaluate(h, landscape)
                    return h, verdict, None
                except Exception as exc:
                    return h, None, exc

        results = await asyncio.gather(
            *[_evaluate(h) for h in current_pool],
            return_exceptions=True,
        )

        # Process verdicts
        advance: list[StructuredHypothesis] = []
        revise: list[tuple[StructuredHypothesis, TribunalVerdict]] = []
        abandoned = 0

        for result in results:
            if isinstance(result, Exception):
                logger.error("tribunal.eval_failed", error=str(result))
                continue
            h, verdict, error = result
            if error is not None:
                logger.error("tribunal.eval_failed", hypothesis_id=h.id, error=str(error))
                advance.append(h)
                continue

            if verdict is None:
                logger.error("tribunal.eval_failed", hypothesis_id=h.id, error="missing verdict")
                advance.append(h)
                continue

            verdict.mutation_cycle = cycle + 1
            all_verdicts[h.id] = verdict

            # Backpropagate score to IdeaTree
            node_id = hyp_to_node.get(h.id)
            if node_id:
                score = _compute_verdict_score(verdict)
                idea_tree.backpropagate(node_id, score)

            if verdict.overall_verdict == "advance":
                advance.append(h)
            elif verdict.overall_verdict == "revise":
                # Check if this cycle's mutation trigger fires
                if cycle_config["trigger"](verdict):
                    revise.append((h, verdict))
                else:
                    advance.append(h)
            else:
                abandoned += 1
                if node_id and node_id in idea_tree.nodes:
                    idea_tree.nodes[node_id].is_pruned = True

        logger.info(
            "tribunal.cycle_done",
            cycle=cycle + 1,
            target=cycle_config["target"],
            advanced=len(advance),
            revising=len(revise),
            abandoned=abandoned,
        )
        advanced_total.extend(advance)

        # Evolve "revise" hypotheses with cycle-specific mutation
        evolved: list[StructuredHypothesis] = []
        if revise:
            evolve_tasks = [evolver.evolve(h, v) for h, v in revise]
            evolve_results = await asyncio.gather(*evolve_tasks, return_exceptions=True)
            for i, result in enumerate(evolve_results):
                if isinstance(result, StructuredHypothesis):
                    evolved.append(result)
                    parent_h = revise[i][0]
                    parent_node_id = hyp_to_node.get(parent_h.id)
                    new_node = idea_tree.add_node(
                        result,
                        parent_id=parent_node_id,
                        mutation_op=cycle_config["mutation_key"],
                    )
                    hyp_to_node[result.id] = new_node.node_id
                elif isinstance(result, Exception):
                    logger.warning("tribunal.evolve_failed", error=str(result))

        # Mechanism Validator gate after final cycle
        if cycle == max_cycles - 1 and evolved:
            gate_pass: list[StructuredHypothesis] = []
            for eh in evolved:
                try:
                    mech = await panel._mechanism.validate(eh)
                    if mech.is_logically_valid:
                        gate_pass.append(eh)
                    else:
                        logger.info("tribunal.mechanism_gate_blocked", hypothesis_id=eh.id)
                        nid = hyp_to_node.get(eh.id)
                        if nid and nid in idea_tree.nodes:
                            idea_tree.nodes[nid].is_pruned = True
                except Exception:
                    gate_pass.append(eh)
            evolved = gate_pass

        current_pool = evolved

        if not evolved:
            logger.info("tribunal.converged", cycle=cycle + 1)
            break

    # Final pool: all advanced + last evolved batch
    refined_by_id: dict[str, StructuredHypothesis] = {}
    for hypothesis in [*advanced_total, *current_pool]:
        refined_by_id[hypothesis.id] = hypothesis
    refined = list(refined_by_id.values())

    if progress:
        await progress("tribunal", f"Tribunal complete: {len(refined)} hypotheses survived", max_cycles, max_cycles)

    return {
        "tribunal_verdicts": all_verdicts,
        "refined_hypotheses": refined,
        "refinement_cycle": min(cycle + 1, max_cycles),  # type: ignore[possibly-undefined]
        "idea_tree": idea_tree,
    }
