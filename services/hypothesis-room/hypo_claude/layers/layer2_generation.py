"""Layer 2 — Multi-Strategy Hypothesis Generation.

Fans out 7 strategies in parallel, merges + deduplicates results.
"""

from __future__ import annotations

from typing import Any, Callable

import structlog

from shared.dedup import deduplicate_by_cosine

from hypo_claude.agents.generators import MultiStrategyGenerator
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import ResearchLandscape, ResearchSpaceMap, StructuredHypothesis

logger = structlog.get_logger(__name__)


def _hypothesis_text(h: StructuredHypothesis) -> str:
    """Combine key fields into a single text for deduplication."""
    return f"{h.title} {h.condition} {h.intervention} {h.prediction} {h.mechanism}"


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 2: Generate hypotheses via 7 parallel strategies."""

    landscape: ResearchLandscape = state["research_landscape"]
    space_map: ResearchSpaceMap = state["research_space_map"]
    config = state.get("config")
    max_per = config.max_hypotheses_per_strategy if config else 5
    max_concurrent = config.max_concurrent_strategies if hasattr(config, "max_concurrent_strategies") else 4
    dedup_threshold = config.dedup_threshold if config else 0.80

    if progress:
        await progress("generation", "Running 7 generation strategies...", 0, 4)

    # Fan out all 7 strategies
    generator = MultiStrategyGenerator(llm)
    strategy_outputs = await generator.generate_all(
        landscape, space_map,
        num_per_strategy=max_per,
        max_concurrent=max_concurrent,
    )

    if progress:
        total = sum(len(v) for v in strategy_outputs.values())
        await progress("generation", f"Generated {total} raw hypotheses", 1, 4)

    # Merge into flat pool
    all_hypotheses: list[StructuredHypothesis] = []
    for hyps in strategy_outputs.values():
        all_hypotheses.extend(hyps)

    if progress:
        await progress("generation", "Deduplicating...", 2, 4)

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

    if progress:
        await progress("generation", f"Generation complete: {len(deduped)} unique hypotheses", 3, 4)

    return {
        "strategy_outputs": {k: [h.model_dump() for h in v] for k, v in strategy_outputs.items()},
        "hypothesis_pool": deduped,
    }
