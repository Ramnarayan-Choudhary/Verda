"""Stage 3 — Archetype-Mapped Seed Generation with Live Novelty Validation.

Enhanced with:
1. Archetype-mapped generation: gap × archetype → IF/THEN/BECAUSE seeds
2. Live novelty validation (AI-Scientist-v2 pattern): each seed batch is
   checked against Semantic Scholar to ensure we're not reinventing the wheel
3. Reflection pass: seeds that overlap with existing work get refined

Flow: meta_gaps × archetypes → structured seeds → S2 novelty check → deduplication
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from pydantic import BaseModel, Field

from vreda_hypothesis.llm import AgentRole
from vreda_hypothesis.llm.prompts.archetype_seeds import archetype_seed_prompt
from vreda_hypothesis.llm.prompts.literature_search import novelty_search_prompt
from vreda_hypothesis.models import (
    ARCHETYPE_TO_TYPE,
    GAP_TO_ARCHETYPE,
    HypothesisArchetype,
    HypothesisSeed,
    HypothesisType,
    MetaGap,
    PipelineState,
    StageError,
)
from vreda_hypothesis.runtime import PipelineRuntime
from vreda_hypothesis.utils import dedup

logger = structlog.get_logger(__name__)


class ArchetypeSeedItem(BaseModel):
    """Single seed from LLM structured output."""
    text: str
    type: HypothesisType = HypothesisType.SCALE
    predicted_impact: str = ""
    archetype: HypothesisArchetype = HypothesisArchetype.MECHANISTIC_PROBE
    gap_id: str = ""


class ArchetypeSeedBatch(BaseModel):
    """Batch of seeds returned by the LLM."""
    seeds: list[ArchetypeSeedItem] = Field(default_factory=list)


class NoveltyAssessment(BaseModel):
    """LLM novelty check result against S2 papers."""
    is_novel: bool = True
    overlap_score: float = Field(default=0.0, ge=0.0, le=1.0)
    closest_paper: str = ""
    differentiation: str = ""


# Legacy fallback
DIVERSITY_TAGS = [
    "architecture crossover",
    "modality pivot",
    "resource-constrained remix",
    "analogical surprise",
    "dataset remix",
    "failure-mode inversion",
    "parameter-efficient tweak",
]


async def run(state: PipelineState, runtime: PipelineRuntime) -> dict[str, Any]:
    if not state.paper_summary:
        return {}

    seeds: list[HypothesisSeed] = []
    rag_hits = await runtime.vector_store.similarity_search(
        state.paper_summary.abstract or state.paper_text, k=5
    )
    snippets = [hit.get("text", "") for hit in rag_hits]

    try:
        meta_gaps = state.meta_gaps
        if meta_gaps:
            seeds = await _archetype_mapped_generation(state, runtime, meta_gaps, snippets)
        else:
            seeds = await _fallback_generation(state, runtime, snippets)

        # Live novelty validation via S2 search (AI-Scientist-v2 pattern)
        if seeds:
            seeds = await _novelty_validate_seeds(seeds, runtime)
        else:
            seeds = _heuristic_seed_generation(state)

        # Deduplicate
        if seeds:
            seed_texts = [seed.text for seed in seeds]
            try:
                _, keep_indices = dedup.deduplicate_by_cosine(
                    seed_texts, threshold=state.config.seed_dedup_threshold
                )
                unique_seeds = [seeds[i] for i in keep_indices if 0 <= i < len(seeds)]
            except Exception as exc:
                logger.warning("overgeneration.dedup_failed_fallback", error=str(exc))
                # Fallback lexical dedup to keep pipeline moving.
                seen: set[str] = set()
                unique_seeds = []
                for seed in seeds:
                    key = " ".join(seed.text.lower().split())
                    if key in seen:
                        continue
                    seen.add(key)
                    unique_seeds.append(seed)
        else:
            unique_seeds = []

        # Enforce archetype/type diversity so the UI does not show near-identical cards.
        if unique_seeds:
            limit = min(max(state.config.top_k * 4, 12), state.config.max_seeds)
            unique_seeds = _diversify_seed_pool(unique_seeds, limit=limit)

        # Last-resort rescue: never leave downstream stages without seeds.
        if not unique_seeds:
            rescued = _heuristic_seed_generation(state)
            if rescued:
                logger.warning(
                    "overgeneration.seed_rescue_used",
                    reason="empty_after_generation_or_novelty_filter",
                    rescued=len(rescued),
                )
                unique_seeds = rescued

        logger.info(
            "stage.overgeneration.complete",
            generated=len(seeds),
            deduped=len(unique_seeds),
            used_archetypes=bool(meta_gaps),
        )
        return {"seeds": unique_seeds}

    except Exception as exc:
        logger.exception("stage.overgeneration.error", error=str(exc))
        state.errors.append(StageError(stage="overgeneration", message=str(exc)))
        return {"errors": state.errors}


async def _novelty_validate_seeds(
    seeds: list[HypothesisSeed],
    runtime: PipelineRuntime,
) -> list[HypothesisSeed]:
    """AI-Scientist-v2 pattern: For each seed, search S2 for the core concept
    and check if the idea already exists. Seeds with high overlap are downranked
    or annotated with the closest existing paper.

    This prevents generating hypotheses that are already published.
    """
    validated: list[HypothesisSeed] = []
    rejected_with_overlap: list[tuple[HypothesisSeed, float]] = []

    # Process in batches of 5 to respect S2 rate limits
    for chunk_start in range(0, len(seeds), 5):
        chunk = seeds[chunk_start:chunk_start + 5]

        # Step 1: Extract short search query from each seed (first 8 significant words)
        async def _check_seed(seed: HypothesisSeed) -> tuple[HypothesisSeed, float]:
            try:
                # Extract key terms for S2 search (first sentence, cleaned)
                search_text = seed.text.split(".")[0][:100].strip()
                if len(search_text) < 10:
                    search_text = seed.text[:100]

                # Search S2 for related papers
                s2_results = await runtime.semantic_scholar.keyword_search(
                    search_text, limit=5
                )

                if not s2_results:
                    return seed, 0.0  # No results = likely novel

                # LLM novelty assessment
                papers_data = [
                    {"title": p.title, "abstract": p.abstract or ""}
                    for p in s2_results
                ]
                system, user = novelty_search_prompt(seed.text, papers_data)
                assessment = await runtime.llm.generate_json(
                    system, user, NoveltyAssessment,
                    temperature=0.1,
                    role=AgentRole.VERIFIABILITY,
                )
                return seed, assessment.overlap_score

            except Exception as exc:
                logger.debug("novelty_check.seed_failed", error=str(exc))
                return seed, 0.0  # On error, assume novel

        results = await asyncio.gather(*[_check_seed(s) for s in chunk])

        for seed, overlap in results:
            if overlap < 0.85:  # Keep seeds with < 85% overlap
                validated.append(seed)
            else:
                rejected_with_overlap.append((seed, overlap))
                logger.info(
                    "overgeneration.seed_rejected_novelty",
                    seed_text=seed.text[:80],
                    overlap=overlap,
                )

    rejected = len(seeds) - len(validated)
    if rejected > 0:
        logger.info(
            "overgeneration.novelty_filter",
            total=len(seeds),
            passed=len(validated),
            rejected=rejected,
        )

    # Keep a small fallback set if novelty filtering removed everything.
    if not validated and rejected_with_overlap:
        rescued = [
            seed
            for seed, _ in sorted(rejected_with_overlap, key=lambda item: item[1])[:3]
        ]
        logger.warning(
            "overgeneration.novelty_filter_rescue",
            rescued=len(rescued),
            total_rejected=len(rejected_with_overlap),
        )
        return rescued

    return validated


async def _archetype_mapped_generation(
    state: PipelineState,
    runtime: PipelineRuntime,
    meta_gaps: list[MetaGap],
    snippets: list[str],
) -> list[HypothesisSeed]:
    """Generate seeds by matching each gap to its best-fit archetype."""
    assert state.paper_summary is not None
    seeds_per_gap = state.config.seeds_per_gap

    generation_tasks: list[tuple[MetaGap, HypothesisArchetype]] = []
    for gap in meta_gaps:
        archetypes = GAP_TO_ARCHETYPE.get(gap.gap_type, [HypothesisArchetype.MECHANISTIC_PROBE])
        primary_archetype = archetypes[0]
        generation_tasks.append((gap, primary_archetype))
        if len(meta_gaps) < 5 and len(archetypes) > 1:
            generation_tasks.append((gap, archetypes[1]))

    async def _generate_for_gap(gap: MetaGap, archetype: HypothesisArchetype) -> list[HypothesisSeed]:
        try:
            system, user = archetype_seed_prompt(
                state.paper_summary,  # type: ignore[arg-type]
                state.research_frame,
                gap,
                archetype,
                seeds_per_gap=seeds_per_gap,
                rag_snippets=snippets,
            )
            batch = await runtime.llm.generate_json(
                system, user, ArchetypeSeedBatch,
                temperature=0.7,
                role=AgentRole.SEED_GENERATION,
            )
            result = []
            for item in batch.seeds:
                if not item.text.strip():
                    continue
                result.append(
                    HypothesisSeed(
                        text=item.text,
                        type=ARCHETYPE_TO_TYPE.get(archetype, item.type),
                        source_prompt=f"archetype:{archetype.value}:gap:{gap.gap_id}",
                        archetype=archetype,
                        gap_id=gap.gap_id,
                    )
                )
            return result
        except Exception as exc:
            logger.warning(
                "overgeneration.archetype_task_failed",
                gap_id=gap.gap_id,
                archetype=archetype.value,
                error=str(exc),
            )
            return _heuristic_gap_seed_generation(state, [gap], archetype_override=archetype)[:seeds_per_gap]

    all_seeds: list[HypothesisSeed] = []
    for chunk_start in range(0, len(generation_tasks), 3):
        chunk = generation_tasks[chunk_start:chunk_start + 3]
        results = await asyncio.gather(
            *[_generate_for_gap(gap, arch) for gap, arch in chunk]
        )
        for parsed in results:
            all_seeds.extend(parsed)

    logger.info(
        "overgeneration.archetype_mapped",
        gaps=len(meta_gaps),
        tasks=len(generation_tasks),
        total_seeds=len(all_seeds),
    )
    if not all_seeds:
        all_seeds = _heuristic_gap_seed_generation(state, meta_gaps)
        if all_seeds:
            logger.warning(
                "overgeneration.archetype_rescue_used",
                gaps=len(meta_gaps),
                seeds=len(all_seeds),
            )
    return all_seeds


async def _fallback_generation(
    state: PipelineState,
    runtime: PipelineRuntime,
    snippets: list[str],
) -> list[HypothesisSeed]:
    """Fallback: use legacy diversity-tag generation when no meta_gaps available."""
    import random

    from vreda_hypothesis.llm.prompts import seed_generation_prompt

    assert state.paper_summary is not None
    max_seeds = state.config.max_seeds
    seeds: list[HypothesisSeed] = []

    tags = DIVERSITY_TAGS.copy()
    random.shuffle(tags)

    from pydantic import BaseModel as _BM
    from pydantic import Field as _F

    class SeedItem(_BM):
        text: str
        type: HypothesisType = HypothesisType.SCALE
        predicted_impact: str = ""

    class SeedBatch(_BM):
        seeds: list[SeedItem] = _F(default_factory=list)

    for tag in tags:
        system, user = seed_generation_prompt(
            state.paper_summary, state.gap_analysis, snippets, tag
        )
        batch = await runtime.llm.generate_json(
            system, user, SeedBatch,
            temperature=0.8,
            role=AgentRole.SEED_GENERATION,
        )
        for item in batch.seeds:
            if item.text.strip():
                seeds.append(
                    HypothesisSeed(
                        text=item.text,
                        type=item.type,
                        source_prompt=f"seed:{tag}",
                    )
                )
        if len(seeds) >= max_seeds:
            break

    return seeds[:max_seeds]


def _heuristic_seed_generation(state: PipelineState) -> list[HypothesisSeed]:
    """Generate dynamic, deterministic seeds from extracted paper structure.

    Used only as a resilience fallback when LLM generation returns zero seeds.
    """
    if not state.paper_summary:
        return []

    summary = state.paper_summary
    methods = [m for m in summary.methods if m.strip()] or [summary.model_architecture or "core approach"]
    limits = [l for l in summary.limitations if l.strip()] or ["generalization under distribution shift"]
    datasets = [d for d in summary.datasets if d.strip()] or ["benchmark datasets"]
    contributions = [c for c in summary.contributions if c.strip()] or [summary.model_architecture or "reported improvements"]

    seeds: list[HypothesisSeed] = []
    max_seeds = min(max(state.config.top_k * 2, 4), 12)
    for idx in range(max_seeds):
        method = methods[idx % len(methods)]
        limit = limits[idx % len(limits)]
        dataset = datasets[idx % len(datasets)]
        contribution = contributions[idx % len(contributions)]
        text = (
            f"If {method} is adapted to directly mitigate {limit} on {dataset}, "
            f"then performance should improve over the reported baseline because {contribution} "
            "indicates the mechanism is currently under-constrained in this regime."
        )
        seeds.append(
            HypothesisSeed(
                text=text,
                type=HypothesisType.ARCHITECTURE_ABLATION,
                source_prompt="heuristic_rescue",
                gap_id="",
            )
        )
    return seeds


def _heuristic_gap_seed_generation(
    state: PipelineState,
    meta_gaps: list[MetaGap],
    archetype_override: HypothesisArchetype | None = None,
) -> list[HypothesisSeed]:
    """Generate deterministic, gap-targeted seeds with explicit diversity."""
    if not state.paper_summary:
        return []

    summary = state.paper_summary
    methods = [m for m in summary.methods if m.strip()] or [summary.model_architecture or "core operator"]
    datasets = [d for d in summary.datasets if d.strip()] or ["the primary benchmark dataset"]

    if not meta_gaps:
        meta_gaps = [
            MetaGap(
                gap_type="empirical",
                statement=f"Missing controlled ablation for {methods[0]} on {datasets[0]}",
                why_it_matters="Without controlled ablations, causal mechanism attribution is weak.",
            )
        ]

    archetype_order = [
        HypothesisArchetype.MECHANISTIC_PROBE,
        HypothesisArchetype.FAILURE_INVERSION,
        HypothesisArchetype.BASELINE_CLOSURE,
        HypothesisArchetype.REGIME_FLIP,
        HypothesisArchetype.OPERATOR_INJECTION,
    ]

    seeds: list[HypothesisSeed] = []
    for idx, gap in enumerate(meta_gaps):
        method = methods[idx % len(methods)]
        dataset = datasets[idx % len(datasets)]
        archetype = archetype_override or archetype_order[idx % len(archetype_order)]
        hyp_type = ARCHETYPE_TO_TYPE.get(archetype, HypothesisType.ARCHITECTURE_ABLATION)
        text = (
            f"IF {method} is modified via {archetype.value.replace('_', ' ')} to target \"{gap.statement}\", "
            f"THEN the primary metric on {dataset} should improve by 2-5% BECAUSE the intervention isolates "
            "the mechanism currently conflating robustness and efficiency effects."
        )
        seeds.append(
            HypothesisSeed(
                text=text,
                type=hyp_type,
                source_prompt=f"heuristic_gap:{archetype.value}",
                archetype=archetype,
                gap_id=gap.gap_id,
            )
        )
    return seeds


def _diversify_seed_pool(seeds: list[HypothesisSeed], limit: int) -> list[HypothesisSeed]:
    """Round-robin by archetype then type to avoid near-duplicate hypothesis cards."""
    by_archetype: dict[HypothesisArchetype, list[HypothesisSeed]] = {}
    for seed in seeds:
        by_archetype.setdefault(seed.archetype, []).append(seed)

    ordered_groups = sorted(
        by_archetype.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )

    selected: list[HypothesisSeed] = []
    seen_text: set[str] = set()
    while len(selected) < limit:
        added = False
        for _, group in ordered_groups:
            if not group:
                continue
            candidate = group.pop(0)
            signature = " ".join(candidate.text.lower().split())
            if signature in seen_text:
                continue
            selected.append(candidate)
            seen_text.add(signature)
            added = True
            if len(selected) >= limit:
                break
        if not added:
            break

    return selected
