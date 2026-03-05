"""Stage 4 — Enhanced filtering: novelty + budget + verifiability + concreteness.

New filters added:
- MVE concreteness check: can this seed be expressed as 5 concrete experiment steps?
- Real dataset validation: does the seed reference a real, named dataset?

Combined score reweighted:
  novelty×0.3 + verifiability×0.25 + budget×0.2 + concreteness×0.25
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import structlog
from pydantic import BaseModel, Field

from vreda_hypothesis.knowledge import PaperKnowledgeGraph
from vreda_hypothesis.llm import AgentRole
from vreda_hypothesis.llm.prompts import verifiability_prompt
from vreda_hypothesis.models import HypothesisSeed, PipelineState, ScoredSeed, StageError
from vreda_hypothesis.runtime import PipelineRuntime
from vreda_hypothesis.utils.cost import estimate_budget

logger = structlog.get_logger(__name__)

# Limit concurrent LLM calls to avoid rate limits
MAX_CONCURRENT_FILTER = 15


class VerifiabilityPayload(BaseModel):
    verifiability: int = Field(ge=1, le=10)
    notes: str = ""


class ConcretenessPayload(BaseModel):
    """MVE concreteness check — can this be a 5-step experiment?"""
    concreteness: int = Field(ge=1, le=10)
    has_real_dataset: bool = False
    has_quantitative_prediction: bool = False
    mve_feasible: bool = False
    notes: str = ""


def _concreteness_prompt(seed_text: str) -> tuple[str, str]:
    """Prompt for MVE concreteness scoring."""
    system = (
        "Score how concrete and experiment-ready this research hypothesis seed is (1-10).\n\n"
        "Check:\n"
        "1. Does it reference a REAL, NAMED dataset (ImageNet, GLUE, C4, etc.)? → has_real_dataset\n"
        "2. Does the prediction contain a NUMBER or bounded direction (+5% F1, 2x speedup)? → has_quantitative_prediction\n"
        "3. Could you write a 5-step Minimum Viable Experiment for this? → mve_feasible\n\n"
        "Scoring guide:\n"
        "- 9-10: Fully specified experiment — dataset, metric, intervention, predicted magnitude all present\n"
        "- 7-8: Mostly specified — 1 element needs clarification\n"
        "- 4-6: Direction is clear but multiple experiment details are missing\n"
        "- 1-3: Vague research direction, not an experiment\n\n"
        'Return JSON: {"concreteness": int, "has_real_dataset": bool, '
        '"has_quantitative_prediction": bool, "mve_feasible": bool, "notes": "brief explanation"}'
    )
    user = f"Seed: {seed_text}"
    return system, user


async def run(state: PipelineState, runtime: PipelineRuntime) -> dict[str, Any]:
    if not state.seeds:
        return {}

    graph: PaperKnowledgeGraph = state.knowledge_graph or PaperKnowledgeGraph()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FILTER)

    async def _score_seed(seed: HypothesisSeed) -> ScoredSeed:
        """Score a single seed — runs concurrently with semaphore control."""
        async with semaphore:
            # Novelty: KG overlap + vector similarity
            novelty_signal = graph.novelty_signal(seed.text)
            rag_hits = await runtime.vector_store.similarity_search(seed.text, k=3)
            max_vector_sim = rag_hits[0]["score"] if rag_hits else 0.0
            novelty_score = max(0.0, 1.0 - max(novelty_signal.overlap_ratio, max_vector_sim))

            # Budget: heuristic cost estimate
            budget = estimate_budget(seed.text)

            # Verifiability: LLM quick check (FAST tier)
            try:
                v_system, v_user = verifiability_prompt(seed.text)
                verifiability = await runtime.llm.generate_json(
                    v_system, v_user, VerifiabilityPayload,
                    temperature=0.1,
                    role=AgentRole.VERIFIABILITY,
                )
            except Exception as exc:
                logger.warning("filtering.verifiability_fallback", error=str(exc))
                verifiability = _heuristic_verifiability(seed.text)

            # Concreteness: MVE feasibility + dataset + prediction check
            try:
                c_system, c_user = _concreteness_prompt(seed.text)
                concreteness = await runtime.llm.generate_json(
                    c_system, c_user, ConcretenessPayload,
                    temperature=0.1,
                    role=AgentRole.VERIFIABILITY,
                )
            except Exception as exc:
                logger.warning("filtering.concreteness_fallback", error=str(exc))
                concreteness = _heuristic_concreteness(seed.text)

            verif_normalized = verifiability.verifiability / 10
            concrete_normalized = concreteness.concreteness / 10
            budget_score = _budget_to_score(budget["cost_with_contingency_usd"])

            # Reweighted combined score
            combined = (
                novelty_score * 0.30
                + verif_normalized * 0.25
                + budget_score * 0.20
                + concrete_normalized * 0.25
            )

            # Penalty for missing basics
            if not concreteness.has_real_dataset:
                combined *= 0.8  # 20% penalty for no real dataset
            if not concreteness.has_quantitative_prediction:
                combined *= 0.85  # 15% penalty for no quantitative prediction

            discard_reason = None
            if combined < 0.2:
                discard_reason = "Score too low"
            elif not concreteness.mve_feasible and concrete_normalized < 0.3:
                discard_reason = "Not experiment-ready"

            return ScoredSeed(
                seed=seed,
                novelty_score=novelty_score,
                budget_estimate_usd=budget["cost_with_contingency_usd"],
                verifiability_score=verif_normalized,
                concreteness_score=concrete_normalized,
                combined_score=combined,
                discard_reason=discard_reason,
            )

    try:
        # Run all seed scoring in parallel (semaphore limits concurrency)
        scored = await asyncio.gather(*[_score_seed(seed) for seed in state.seeds])

        # Filter out discarded seeds, then take top-K×5
        valid = [s for s in scored if s.discard_reason is None]
        discarded = [s for s in scored if s.discard_reason is not None]
        if not valid and discarded:
            rescue_count = min(max(state.config.top_k, 3), len(discarded))
            valid = sorted(discarded, key=lambda item: item.combined_score, reverse=True)[:rescue_count]
            for item in valid:
                item.discard_reason = None
            logger.warning(
                "stage.filtering.rescued_all_discarded",
                rescued=len(valid),
                original_discarded=len(discarded),
            )

        limit = min(100, max(state.config.top_k * 5, 20))
        sorted_valid = sorted(valid, key=lambda item: item.combined_score, reverse=True)
        filtered = _select_diverse_scored_seeds(sorted_valid, limit=limit)

        logger.info(
            "stage.filtering.complete",
            kept=len(filtered),
            discarded=len(discarded),
            original=len(state.seeds),
        )
        return {"filtered_seeds": filtered}
    except Exception as exc:
        logger.exception("stage.filtering.error", error=str(exc))
        state.errors.append(StageError(stage="filtering", message=str(exc)))
        return {"errors": state.errors}


def _budget_to_score(cost_usd: float) -> float:
    if cost_usd <= 5:
        return 1.0
    if cost_usd <= 20:
        return 0.7
    if cost_usd <= 50:
        return 0.4
    if cost_usd <= 100:
        return 0.2
    return 0.05


def _heuristic_verifiability(seed_text: str) -> VerifiabilityPayload:
    text = seed_text.lower()
    has_if_then = "if " in text and " then " in text
    has_number = bool(re.search(r"\b\d+(\.\d+)?\s*(%|x|point|points|ms|s|hours?)?\b", text))
    score = 5 + (2 if has_if_then else 0) + (2 if has_number else 0)
    return VerifiabilityPayload(verifiability=max(1, min(10, score)), notes="heuristic fallback")


def _heuristic_concreteness(seed_text: str) -> ConcretenessPayload:
    text = seed_text.lower()
    dataset_markers = (
        "imagenet", "cifar", "glue", "superglue", "mmlu", "wmt", "c4", "swe-bench",
        "mnist", "squad", "wiki", "benchmark",
    )
    has_dataset = any(marker in text for marker in dataset_markers)
    has_quant = bool(re.search(r"\b\d+(\.\d+)?\s*(%|x|point|points|ms|s|hours?)?\b", text))
    has_intervention = any(word in text for word in ("replace", "modify", "adapt", "inject", "ablate", "constrain"))
    base = 4 + (2 if has_dataset else 0) + (2 if has_quant else 0) + (1 if has_intervention else 0)
    return ConcretenessPayload(
        concreteness=max(1, min(10, base)),
        has_real_dataset=has_dataset,
        has_quantitative_prediction=has_quant,
        mve_feasible=has_intervention and (has_dataset or has_quant),
        notes="heuristic fallback",
    )


def _select_diverse_scored_seeds(scored: list[ScoredSeed], limit: int) -> list[ScoredSeed]:
    """Prefer high-scoring seeds while keeping type and text diversity."""
    if len(scored) <= limit:
        return scored

    by_type: dict[str, list[ScoredSeed]] = {}
    for item in scored:
        by_type.setdefault(item.seed.type.value, []).append(item)

    groups = list(by_type.values())
    selected: list[ScoredSeed] = []
    seen_signatures: set[str] = set()
    while len(selected) < limit:
        added = False
        for group in groups:
            if not group:
                continue
            candidate = group.pop(0)
            signature = " ".join(candidate.seed.text.lower().split())
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            selected.append(candidate)
            added = True
            if len(selected) >= limit:
                break
        if not added:
            break

    if len(selected) < limit:
        for item in scored:
            if len(selected) >= limit:
                break
            signature = " ".join(item.seed.text.lower().split())
            if signature in seen_signatures:
                continue
            selected.append(item)
            seen_signatures.add(signature)
    return selected
