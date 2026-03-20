from __future__ import annotations

from collections import defaultdict

import structlog

from hypo_gpt.agents.generators import LEGACY_MAPPING, StrategyGenerator
from hypo_gpt.models import PipelineState, StructuredHypothesis
from shared.dedup import deduplicate_by_cosine

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    if state.research_landscape is None or state.research_space_map is None:
        state.errors.append("Layer2: missing prerequisites")
        return state

    generator = StrategyGenerator()
    if state.config.pipeline_version == "v1":
        strategy_outputs = await generator.generate(
            state.research_landscape,
            state.research_space_map,
            per_strategy=state.config.hypotheses_per_strategy,
        )
        state.strategy_outputs = strategy_outputs

        pooled = [item for items in strategy_outputs.values() for item in items]
        if not pooled:
            state.errors.append("Layer2: no hypotheses generated")
            state.hypothesis_pool = []
            return state

        dedup_texts = [f"{hyp.intervention} || {hyp.prediction} || {hyp.mechanism}" for hyp in pooled]
        _, keep_indices = deduplicate_by_cosine(dedup_texts, threshold=0.72)
        state.hypothesis_pool = [pooled[index] for index in keep_indices]
        logger.info("hypo_gpt.layer2.complete.v1", pooled=len(pooled), deduped=len(state.hypothesis_pool))
        return state

    idea_tree, skip_strategies = await generator.build_tree(
        research_query=state.research_intent,
        landscape=state.research_landscape,
        space_map=state.research_space_map,
        per_strategy=state.config.hypotheses_per_strategy,
        max_rounds=state.config.max_rounds,
        memory_negatives=state.memory_entries,
    )

    state.idea_tree = idea_tree
    state.hypothesis_pool_v2 = [node.hypothesis for node in idea_tree.nodes.values() if not node.is_pruned]

    strategy_outputs: dict[str, list[StructuredHypothesis]] = defaultdict(list)
    pooled: list[StructuredHypothesis] = []
    for hypothesis in state.hypothesis_pool_v2:
        legacy_strategy = LEGACY_MAPPING.get(hypothesis.strategy, "synthesis_catalyst")
        converted = hypothesis.to_structured()
        strategy_outputs[legacy_strategy].append(converted)
        pooled.append(converted)

    state.strategy_outputs = dict(strategy_outputs)

    if not pooled:
        state.errors.append("Layer2: no hypotheses generated")
        state.hypothesis_pool = []
        return state

    dedup_texts = [f"{hyp.intervention} || {hyp.prediction} || {hyp.mechanism}" for hyp in pooled]
    _, keep_indices = deduplicate_by_cosine(dedup_texts, threshold=0.72)
    hypothesis_pool = [pooled[i] for i in keep_indices]

    structural_seen: set[str] = set()
    structurally_unique: list[StructuredHypothesis] = []
    for hypothesis in hypothesis_pool:
        key = (
            f"{hypothesis.generation_strategy}|{hypothesis.source_gap_id}|"
            f"{' '.join(hypothesis.title.lower().split())[:80]}"
        )
        if key in structural_seen:
            continue
        structural_seen.add(key)
        structurally_unique.append(hypothesis)

    state.hypothesis_pool = structurally_unique

    if len(state.hypothesis_pool) < state.config.min_hypotheses_pool:
        existing_ids = {hyp.id for hyp in state.hypothesis_pool}
        for candidate in pooled:
            if len(state.hypothesis_pool) >= state.config.min_hypotheses_pool:
                break
            if candidate.id in existing_ids:
                continue
            state.hypothesis_pool.append(candidate)
            existing_ids.add(candidate.id)

    logger.info(
        "hypo_gpt.layer2.complete",
        pooled=len(pooled),
        deduped=len(state.hypothesis_pool),
        tree_nodes=len(idea_tree.nodes),
        skip_strategies=skip_strategies,
    )
    return state
