from __future__ import annotations

import structlog

from hypo_gpt.agents.generators import StrategyGenerator
from hypo_gpt.models import PipelineState, StructuredHypothesis
from shared.dedup import deduplicate_by_cosine

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> PipelineState:
    if state.research_landscape is None or state.research_space_map is None:
        state.errors.append("Layer2: missing prerequisites")
        return state

    generator = StrategyGenerator()
    strategy_outputs = await generator.generate(
        state.research_landscape,
        state.research_space_map,
        per_strategy=state.config.hypotheses_per_strategy,
    )
    state.strategy_outputs = strategy_outputs

    pooled: list[StructuredHypothesis] = []
    for items in strategy_outputs.values():
        pooled.extend(items)

    if not pooled:
        state.errors.append("Layer2: no hypotheses generated")
        state.hypothesis_pool = []
        return state

    dedup_texts = [f"{h.intervention} || {h.prediction} || {h.mechanism}" for h in pooled]
    _, keep_indices = deduplicate_by_cosine(dedup_texts, threshold=0.72)
    state.hypothesis_pool = [pooled[i] for i in keep_indices]

    # Feasibility floor: keep hypotheses with non-empty minimal test data.
    state.hypothesis_pool = [
        h for h in state.hypothesis_pool
        if h.minimum_viable_test.dataset and h.minimum_viable_test.primary_metric
    ]

    # Structural dedup: remove near-identical variants from same strategy/gap.
    structural_seen: set[str] = set()
    structurally_unique: list[StructuredHypothesis] = []
    for hypothesis in state.hypothesis_pool:
        normalized_title = " ".join(hypothesis.title.lower().split())
        key = f"{hypothesis.generation_strategy}|{hypothesis.source_gap_id}|{normalized_title[:80]}"
        if key in structural_seen:
            continue
        structural_seen.add(key)
        structurally_unique.append(hypothesis)
    state.hypothesis_pool = structurally_unique

    # Ensure enough hypotheses for tribunal without re-introducing duplicates.
    if len(state.hypothesis_pool) < state.config.min_hypotheses_pool:
        existing_ids = {h.id for h in state.hypothesis_pool}
        structural_keys = {
            f"{h.generation_strategy}|{h.source_gap_id}|{' '.join(h.title.lower().split())[:80]}"
            for h in state.hypothesis_pool
        }
        for candidate in pooled:
            if len(state.hypothesis_pool) >= state.config.min_hypotheses_pool:
                break
            if candidate.id in existing_ids:
                continue
            candidate_key = (
                f"{candidate.generation_strategy}|{candidate.source_gap_id}|"
                f"{' '.join(candidate.title.lower().split())[:80]}"
            )
            if candidate_key in structural_keys:
                continue
            state.hypothesis_pool.append(candidate)
            existing_ids.add(candidate.id)
            structural_keys.add(candidate_key)

    logger.info("hypo_gpt.layer2.complete", pooled=len(pooled), deduped=len(state.hypothesis_pool))
    return state
