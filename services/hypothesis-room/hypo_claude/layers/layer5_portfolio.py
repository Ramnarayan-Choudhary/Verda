"""Layer 5 — Strategic Portfolio Construction with 5-slot risk tiers.

Post-processing:
1. LLM-based portfolio construction (slot assignment, rationale)
2. Correlation removal (cosine sim > 0.65 → remove weaker)
3. Strategy diversity rebalancing (no strategy > 2×)
4. Memory blocking integration (if memory context available)
"""

from __future__ import annotations

from typing import Any, Callable

import structlog

from shared.dedup import compute_embeddings, cosine_similarity

from hypo_claude.agents.portfolio import PortfolioConstructor
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import (
    JudgeScore,
    MemoryContext,
    PipelineConfig,
    PortfolioHypothesis,
    ResearchPortfolio,
    StructuredHypothesis,
    TribunalVerdict,
    compute_controversy_score,
    compute_panel_composite,
)

logger = structlog.get_logger(__name__)


def _hypothesis_text(h: StructuredHypothesis) -> str:
    return f"{h.title} {h.condition} {h.intervention} {h.prediction} {h.mechanism}"


def _remove_correlated(
    portfolio: ResearchPortfolio,
    threshold: float = 0.65,
) -> ResearchPortfolio:
    """Remove hypotheses that are too similar to already-selected ones."""
    if len(portfolio.hypotheses) <= 1:
        return portfolio

    texts = [_hypothesis_text(ph.hypothesis) for ph in portfolio.hypotheses]
    embeddings = compute_embeddings(texts)

    keep: list[int] = [0]  # Always keep the top-ranked one
    for i in range(1, len(portfolio.hypotheses)):
        correlated = False
        for j in keep:
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim > threshold:
                correlated = True
                logger.info(
                    "portfolio.correlated_removed",
                    removed=portfolio.hypotheses[i].hypothesis.title[:40],
                    similar_to=portfolio.hypotheses[j].hypothesis.title[:40],
                    similarity=round(sim, 3),
                )
                break
        if not correlated:
            keep.append(i)

    portfolio.hypotheses = [portfolio.hypotheses[i] for i in keep]
    return portfolio


def _rebalance_strategy_diversity(portfolio: ResearchPortfolio) -> ResearchPortfolio:
    """Ensure no single strategy dominates (> 2 slots)."""
    if len(portfolio.hypotheses) <= 2:
        return portfolio

    strategy_count: dict[str, int] = {}
    for ph in portfolio.hypotheses:
        s = ph.hypothesis.generation_strategy
        strategy_count[s] = strategy_count.get(s, 0) + 1

    max_per_strategy = 2
    rebalanced: list[PortfolioHypothesis] = []
    strategy_used: dict[str, int] = {}

    for ph in portfolio.hypotheses:
        s = ph.hypothesis.generation_strategy
        used = strategy_used.get(s, 0)
        if used < max_per_strategy:
            rebalanced.append(ph)
            strategy_used[s] = used + 1
        else:
            logger.info(
                "portfolio.strategy_capped",
                strategy=s,
                removed=ph.hypothesis.title[:40],
            )

    portfolio.hypotheses = rebalanced
    return portfolio


async def run(state: dict[str, Any], llm: LLMProvider, progress: Callable | None = None) -> dict[str, Any]:
    """Layer 5: Construct a balanced research portfolio with post-processing."""

    ranked: list[StructuredHypothesis] = state.get("ranked_hypotheses", [])
    panel_scores: dict[str, list[JudgeScore]] = state.get("panel_scores", {})
    verdicts: dict[str, TribunalVerdict] = state.get("tribunal_verdicts", {})
    controversy_scores: dict[str, float] = state.get("controversy_scores", {})
    config: PipelineConfig = state.get("config", PipelineConfig())
    memory_context: MemoryContext | None = state.get("memory_context")

    if not ranked:
        logger.warning("layer5.no_hypotheses")
        return {"research_portfolio": ResearchPortfolio()}

    if progress:
        await progress("portfolio", "Constructing research portfolio...", 0, 4)

    # Step 1: LLM-based portfolio construction
    constructor = PortfolioConstructor(llm)
    portfolio = await constructor.construct(ranked, panel_scores, verdicts, config)

    # Fill in controversy scores
    for ph in portfolio.hypotheses:
        hid = ph.hypothesis.id
        ph.controversy_score = controversy_scores.get(hid, 0.0)
        if hid in panel_scores:
            ph.panel_composite = compute_panel_composite(panel_scores[hid])

    if progress:
        await progress("portfolio", f"Initial portfolio: {len(portfolio.hypotheses)} hypotheses", 1, 4)

    # Step 2: Remove correlated hypotheses
    portfolio = _remove_correlated(portfolio, threshold=config.dedup_threshold)

    if progress:
        await progress("portfolio", f"After correlation removal: {len(portfolio.hypotheses)}", 2, 4)

    # Step 3: Strategy diversity rebalancing
    portfolio = _rebalance_strategy_diversity(portfolio)

    if progress:
        n = len(portfolio.hypotheses)
        slots = {
            "safe": len(portfolio.safe_hypotheses),
            "balanced": len(portfolio.balanced_hypotheses),
            "moonshot": len(portfolio.moonshot_hypotheses),
        }
        await progress("portfolio", f"Portfolio: {n} hypotheses — {slots}", 4, 4)

    return {"research_portfolio": portfolio}
