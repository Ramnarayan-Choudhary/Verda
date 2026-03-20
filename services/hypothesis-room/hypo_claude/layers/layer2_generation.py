"""Layer 2 — Multi-Strategy Hypothesis Generation.

Fans out 7 strategies in parallel, merges + deduplicates results.
Memory-conditioned: injects negative blocking + positive building from cross-session memory.
Strategy quota rule: no single strategy > 40% of total pool.
"""

from __future__ import annotations

from typing import Any, Callable

import structlog

from shared.dedup import deduplicate_by_cosine

from hypo_claude.agents.generators import MultiStrategyGenerator
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import (
    IdeaTree,
    MemoryContext,
    ResearchLandscape,
    ResearchSpaceMap,
    StructuredHypothesis,
)

logger = structlog.get_logger(__name__)


def _hypothesis_text(h: StructuredHypothesis) -> str:
    """Combine key fields into a single text for deduplication."""
    return f"{h.title} {h.condition} {h.intervention} {h.prediction} {h.mechanism}"


def _apply_strategy_quota(
    all_hypotheses: list[StructuredHypothesis],
    max_fraction: float = 0.40,
) -> list[StructuredHypothesis]:
    """Enforce strategy quota: no single strategy > max_fraction of total pool."""
    if len(all_hypotheses) <= 3:
        return all_hypotheses

    max_per_strategy = max(3, int(len(all_hypotheses) * max_fraction))

    strategy_count: dict[str, int] = {}
    result: list[StructuredHypothesis] = []

    for h in all_hypotheses:
        s = h.generation_strategy or "unknown"
        count = strategy_count.get(s, 0)
        if count < max_per_strategy:
            result.append(h)
            strategy_count[s] = count + 1
        else:
            logger.debug("layer2.quota_skip", strategy=s, title=h.title[:40])

    if len(result) < len(all_hypotheses):
        logger.info(
            "layer2.strategy_quota_applied",
            before=len(all_hypotheses),
            after=len(result),
            distribution=strategy_count,
        )

    return result


def _apply_memory_blocking(
    hypotheses: list[StructuredHypothesis],
    memory_store: Any,
) -> list[StructuredHypothesis]:
    """Remove hypotheses that are too similar to known failures."""
    if not memory_store or memory_store.size == 0:
        return hypotheses

    kept: list[StructuredHypothesis] = []
    blocked = 0
    for h in hypotheses:
        text = _hypothesis_text(h)
        if memory_store.should_block(text, threshold=0.80):
            blocked += 1
        else:
            kept.append(h)

    if blocked:
        logger.info("layer2.memory_blocked", blocked=blocked)
    return kept


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 2: Generate hypotheses via 7 parallel strategies."""

    landscape: ResearchLandscape = state["research_landscape"]
    space_map: ResearchSpaceMap = state["research_space_map"]
    config = state.get("config")
    memory_context: MemoryContext | None = state.get("memory_context")
    memory_store = state.get("memory_store")
    max_per = config.max_hypotheses_per_strategy if config else 5
    max_concurrent = config.max_concurrent_strategies if hasattr(config, "max_concurrent_strategies") else 4
    dedup_threshold = config.dedup_threshold if config else 0.80

    if progress:
        await progress("generation", "Running 7 generation strategies...", 0, 5)

    # Fan out all 7 strategies
    generator = MultiStrategyGenerator(llm)
    strategy_outputs = await generator.generate_all(
        landscape, space_map,
        num_per_strategy=max_per,
        max_concurrent=max_concurrent,
    )

    if progress:
        total = sum(len(v) for v in strategy_outputs.values())
        await progress("generation", f"Generated {total} raw hypotheses", 1, 5)

    # Merge into flat pool
    all_hypotheses: list[StructuredHypothesis] = []
    for hyps in strategy_outputs.values():
        all_hypotheses.extend(hyps)

    # Strategy quota rule: no single strategy > 40%
    all_hypotheses = _apply_strategy_quota(all_hypotheses)

    if progress:
        await progress("generation", "Deduplicating...", 2, 5)

    # Deduplicate by cosine similarity
    if len(all_hypotheses) > 1:
        texts = [_hypothesis_text(h) for h in all_hypotheses]
        _, keep_indices = deduplicate_by_cosine(texts, threshold=dedup_threshold)
        deduped = [all_hypotheses[i] for i in keep_indices]
    else:
        deduped = all_hypotheses

    logger.info(
        "layer2.deduplication",
        before=len(all_hypotheses),
        after=len(deduped),
    )

    # Memory blocking: remove hypotheses similar to known failures
    if memory_store:
        if progress:
            await progress("generation", "Checking memory for known failures...", 3, 5)
        deduped = _apply_memory_blocking(deduped, memory_store)

    # Initialize IdeaTree with seed hypotheses
    idea_tree = IdeaTree()
    for h in deduped:
        idea_tree.add_node(h)

    if progress:
        dist = idea_tree.get_strategy_distribution()
        await progress("generation", f"Generation complete: {len(deduped)} unique hypotheses — {dist}", 5, 5)

    return {
        "strategy_outputs": {k: [h.model_dump() for h in v] for k, v in strategy_outputs.items()},
        "hypothesis_pool": deduped,
        "idea_tree": idea_tree,
    }
