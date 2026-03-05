"""Stage 5 — Multi-Agent Refinement Loop (generate → reflect → debate → evolve).

Enhanced with:
- Reflection loop (AI-Scientist-v2 pattern): after proposer, search S2 for closest
  work and let LLM strengthen the hypothesis against it
- Wrong-example-bank (HypoRefine pattern): failed hypotheses feed evolver
- ResearchFrame + MetaGap context passed to proposer
- Portfolio tag assigned by critic for downstream audit
- Convergence detection: stops early if Elo ratings stabilize
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from pydantic import BaseModel, Field

from vreda_hypothesis.agents import CriticAgent, EvolverAgent, MetaReviewerAgent, ProposerAgent
from vreda_hypothesis.knowledge import PaperKnowledgeGraph
from vreda_hypothesis.llm import AgentRole
from vreda_hypothesis.llm.prompts.reflection import reflection_prompt
from vreda_hypothesis.models import (
    ARCHETYPE_TO_TYPE,
    EnhancedHypothesis,
    FailedSeed,
    HypothesisArchetype,
    HypothesisSeed,
    HypothesisType,
    PipelineState,
    ScoredSeed,
    StageError,
    compute_composite_score,
)
from vreda_hypothesis.runtime import PipelineRuntime
from vreda_hypothesis.utils import elo

logger = structlog.get_logger(__name__)

# Convergence: stop if average Elo change per cycle is below this threshold
ELO_CONVERGENCE_THRESHOLD = 5.0


class ReflectionUpdate(BaseModel):
    """Updated fields from reflection pass."""
    title: str = ""
    statement: str = ""
    description: str = ""
    related_work_summary: str = ""
    novelty_assessment: dict = Field(default_factory=dict)
    testable_prediction: str = ""
    risk_factors: list[str] = Field(default_factory=list)


async def run(state: PipelineState, runtime: PipelineRuntime) -> dict[str, Any]:
    proposer = ProposerAgent(runtime.llm)
    critic = CriticAgent(runtime.llm)
    evolver = EvolverAgent(runtime.llm)
    meta_reviewer = MetaReviewerAgent(runtime.llm)

    graph: PaperKnowledgeGraph = state.knowledge_graph or PaperKnowledgeGraph()

    refined = list(state.refined_hypotheses)
    elo_ratings = dict(state.elo_ratings)
    seed_pool = list(state.filtered_seeds)
    if not seed_pool:
        seed_pool = _rescue_seed_pool(state)
        if seed_pool:
            logger.warning("stage.refinement.seed_pool_rescued", rescued=len(seed_pool))
        else:
            return {}
    meta_notes = list(state.meta_review_notes)
    wrong_examples = list(state.wrong_example_bank)
    max_cycles = state.config.max_cycles
    batch_size = min(12, max(6, state.config.top_k * 2))

    # Build meta_gap lookup for proposer
    meta_gap_map = {g.gap_id: g for g in state.meta_gaps} if state.meta_gaps else {}

    current_cycle = state.refinement_cycle

    try:
        for cycle in range(current_cycle, max_cycles):
            prev_ratings = dict(elo_ratings)

            # Select seeds for this cycle (round-robin through pool, never deplete)
            offset = (cycle * batch_size) % max(len(seed_pool), 1)
            batch = seed_pool[offset : offset + batch_size]
            if len(batch) < batch_size and seed_pool:
                batch.extend(seed_pool[: batch_size - len(batch)])

            if not batch:
                break

            context = _build_context(state, meta_notes)
            gap_summary = _gap_summary(state)

            # Propose — pass ResearchFrame + MetaGap for archetype-aware generation
            proposal_results = await asyncio.gather(
                *[
                    _propose_with_seed(
                        proposer, seed_score, context, gap_summary,
                        research_frame=state.research_frame,
                        meta_gap=meta_gap_map.get(seed_score.seed.gap_id),
                    )
                    for seed_score in batch
                ],
                return_exceptions=True,
            )
            proposals: list[tuple[EnhancedHypothesis, ScoredSeed]] = []
            for seed_score, result in zip(batch, proposal_results, strict=False):
                if isinstance(result, Exception):
                    logger.warning(
                        "refinement.proposal_failed_fallback",
                        seed_id=seed_score.seed.id,
                        error=str(result),
                    )
                    proposals.append((_fallback_hypothesis_from_seed(seed_score, state), seed_score))
                else:
                    proposals.append(result)

            # Reflection pass (AI-Scientist-v2 pattern):
            # Search S2 for closest work, let LLM strengthen hypothesis
            reflected_proposals = await asyncio.gather(
                *[
                    _reflect_on_hypothesis(
                        hypothesis, runtime, cycle + 1
                    )
                    for hypothesis, seed_score in proposals
                ]
            )
            # Replace hypotheses with reflected versions
            proposals = [
                (reflected, seed_score)
                for reflected, (_, seed_score) in zip(reflected_proposals, proposals)
            ]

            # Critic loop — all run in parallel
            assessments = await asyncio.gather(
                *[
                    _critic_with_budget(critic, hypothesis, graph, seed_score)
                    for hypothesis, seed_score in proposals
                ]
            )

            cycle_notes = []
            for (hypothesis, seed_score), assessment in zip(proposals, assessments, strict=False):
                hypothesis.critic_assessment = assessment
                if assessment.revised_scores:
                    hypothesis.scores = assessment.revised_scores
                hypothesis.composite_score = compute_composite_score(hypothesis.scores)
                hypothesis.elo_rating = elo_ratings.get(hypothesis.id, elo.DEFAULT_ELO)
                hypothesis.reflection_rounds_completed += 1

                # Set portfolio tag from critic
                hypothesis.portfolio_tag = assessment.portfolio_tag

                refined.append(hypothesis)

                if assessment.verdict == "strong":
                    elo_ratings[hypothesis.id] = hypothesis.elo_rating + 25
                elif assessment.verdict == "weak":
                    elo_ratings[hypothesis.id] = hypothesis.elo_rating - 25
                    # Wrong-example-bank: track failures (HypoRefine pattern)
                    failure_reasons = "; ".join(assessment.feasibility_issues[:2]) or "Weak verdict"
                    wrong_examples.append(
                        FailedSeed(
                            seed_text=seed_score.seed.text[:300],
                            failure_reason=failure_reasons,
                            gap_id=seed_score.seed.gap_id,
                            archetype=seed_score.seed.archetype,
                        )
                    )
                else:
                    elo_ratings[hypothesis.id] = hypothesis.elo_rating

                cycle_notes.extend(assessment.suggested_improvements)

            meta_feedback = await meta_reviewer.reflect(cycle_notes, cycle + 1)
            meta_notes.extend(meta_feedback.directives)

            # Evolver seeds for next cycle — now with wrong-example-bank context
            top_hypotheses = sorted(refined, key=lambda hyp: hyp.composite_score, reverse=True)[:5]
            evolved_seeds = await evolver.evolve(
                top_hypotheses,
                ",".join(meta_feedback.directives) or "novelty_boost",
                failed_seeds=wrong_examples if wrong_examples else None,
            )
            scored_evolved = await asyncio.gather(
                *[_quick_score_seed(runtime, graph, seed) for seed in evolved_seeds]
            )
            seed_pool.extend(scored_evolved)

            current_cycle = cycle + 1

            # Convergence detection
            if _check_convergence(prev_ratings, elo_ratings):
                logger.info("stage.refinement.converged", cycle=current_cycle)
                break

        logger.info(
            "stage.refinement.complete",
            cycles=current_cycle,
            total_hypotheses=len(refined),
            wrong_examples=len(wrong_examples),
        )
        return {
            "refined_hypotheses": refined,
            "elo_ratings": elo_ratings,
            "refinement_cycle": current_cycle,
            "meta_review_notes": meta_notes,
            "wrong_example_bank": wrong_examples,
        }
    except Exception as exc:
        logger.exception("stage.refinement.error", error=str(exc))
        state.errors.append(StageError(stage="refinement", message=str(exc)))
        return {"errors": state.errors}


def _rescue_seed_pool(state: PipelineState) -> list[ScoredSeed]:
    if state.seeds:
        return [
            ScoredSeed(
                seed=seed,
                novelty_score=0.55,
                budget_estimate_usd=12.0,
                verifiability_score=0.65,
                concreteness_score=0.6,
                combined_score=0.6,
            )
            for seed in state.seeds[: min(len(state.seeds), max(state.config.top_k * 3, 8))]
        ]

    if not state.paper_summary:
        return []

    summary = state.paper_summary
    methods = [m for m in summary.methods if m.strip()] or [summary.model_architecture or "core method"]
    limitations = [l for l in summary.limitations if l.strip()] or ["robustness limitation"]
    datasets = [d for d in summary.datasets if d.strip()] or ["the anchor benchmark"]
    archetypes = [
        HypothesisArchetype.MECHANISTIC_PROBE,
        HypothesisArchetype.FAILURE_INVERSION,
        HypothesisArchetype.REGIME_FLIP,
        HypothesisArchetype.BASELINE_CLOSURE,
    ]

    rescued: list[ScoredSeed] = []
    for idx in range(max(state.config.top_k * 2, 6)):
        archetype = archetypes[idx % len(archetypes)]
        method = methods[idx % len(methods)]
        limitation = limitations[idx % len(limitations)]
        dataset = datasets[idx % len(datasets)]
        text = (
            f"IF {method} is modified using {archetype.value.replace('_', ' ')}, "
            f"THEN the primary metric on {dataset} should improve by 2-5% BECAUSE "
            f"the intervention directly targets {limitation}."
        )
        seed = HypothesisSeed(
            text=text,
            archetype=archetype,
            type=ARCHETYPE_TO_TYPE.get(archetype, HypothesisType.ARCHITECTURE_ABLATION),
            source_prompt="refinement_rescue",
        )
        rescued.append(
            ScoredSeed(
                seed=seed,
                novelty_score=0.58,
                budget_estimate_usd=10.0 + idx,
                verifiability_score=0.66,
                concreteness_score=0.64,
                combined_score=0.63,
            )
        )
    return rescued


def _fallback_hypothesis_from_seed(seed_score: ScoredSeed, state: PipelineState) -> EnhancedHypothesis:
    summary = state.paper_summary
    dataset = (
        summary.datasets[0]
        if summary and summary.datasets
        else "the anchor benchmark"
    )
    method = (
        summary.methods[0]
        if summary and summary.methods
        else "the core method"
    )
    limitation = (
        summary.limitations[0]
        if summary and summary.limitations
        else "the reported limitation"
    )
    archetype = seed_score.seed.archetype or HypothesisArchetype.MECHANISTIC_PROBE
    hyp_type = ARCHETYPE_TO_TYPE.get(archetype, seed_score.seed.type)

    hypothesis = EnhancedHypothesis(
        type=hyp_type,
        archetype=archetype,
        title=f"{archetype.value.replace('_', ' ').title()} Ablation",
        description=seed_score.seed.text,
        short_hypothesis=seed_score.seed.text[:280],
        statement=seed_score.seed.text,
        testable_prediction=f"Improve primary metric on {dataset} by 2-5% over baseline.",
        expected_outcome="A reproducible mechanism-level gain under controlled evaluation.",
        mve=[
            f"Reproduce baseline on {dataset}.",
            f"Apply {archetype.value.replace('_', ' ')} intervention to {method}.",
            "Run ablation with matched compute budget.",
            "Measure primary and efficiency metrics.",
            f"Reject if no significant improvement and no reduction of {limitation}.",
        ],
        falsification_threshold="Dead if no statistically significant gain appears under matched compute.",
        required_modifications=[
            "Implement intervention switch in training/eval pipeline",
            "Add controlled ablation configuration",
            "Add robustness/efficiency logging",
        ],
        estimated_complexity="medium",
        risk_factors=[
            "Intervention may overfit to benchmark-specific artifacts.",
            "Efficiency improvements may trade off against robustness.",
        ],
        related_work_summary="Auto-generated fallback from resilient refinement path.",
        addresses_gap_id=seed_score.seed.gap_id or None,
        reflection_rounds_completed=0,
    )
    hypothesis.scores = DimensionScores(
        novelty=max(40, int(seed_score.novelty_score * 100)),
        feasibility=max(45, int((1.0 - min(seed_score.budget_estimate_usd / 80.0, 1.0)) * 100)),
        impact=62,
        grounding=max(45, int(seed_score.verifiability_score * 100)),
        testability=max(50, int(seed_score.concreteness_score * 100)),
        clarity=64,
    )
    hypothesis.composite_score = compute_composite_score(hypothesis.scores)
    return hypothesis


def _check_convergence(prev_ratings: dict[str, float], current_ratings: dict[str, float]) -> bool:
    """Check if Elo ratings have stabilized (average change below threshold)."""
    if not prev_ratings:
        return False
    common_ids = set(prev_ratings.keys()) & set(current_ratings.keys())
    if len(common_ids) < 3:
        return False
    total_change = sum(abs(current_ratings[h] - prev_ratings[h]) for h in common_ids)
    avg_change = total_change / len(common_ids)
    return avg_change < ELO_CONVERGENCE_THRESHOLD


async def _propose_with_seed(
    proposer: ProposerAgent,
    seed_score: ScoredSeed,
    context: str,
    gap_summary: str,
    research_frame=None,
    meta_gap=None,
) -> tuple[EnhancedHypothesis, ScoredSeed]:
    hypothesis = await proposer.propose(
        seed_score.seed, context, gap_summary,
        seed_score=seed_score,
        research_frame=research_frame,
        meta_gap=meta_gap,
    )
    return hypothesis, seed_score


async def _reflect_on_hypothesis(
    hypothesis: EnhancedHypothesis,
    runtime: PipelineRuntime,
    reflection_round: int,
) -> EnhancedHypothesis:
    """AI-Scientist-v2 reflection pattern: search S2 for the closest existing work,
    then let the LLM strengthen the hypothesis by explicitly differentiating from it.

    This is the key pattern that makes AI-Scientist-v2's ideas high-quality:
    ideas aren't generated in a vacuum — they're refined against real literature.
    """
    try:
        # Extract core concept for S2 search
        search_text = (hypothesis.statement or hypothesis.short_hypothesis or hypothesis.title)[:100]

        # Live search for closest competitor work
        search_results = await runtime.semantic_scholar.keyword_search(search_text, limit=5)

        if not search_results:
            # No competitor found — hypothesis is likely novel, return as-is
            return hypothesis

        # LLM reflection pass
        system, user = reflection_prompt(hypothesis, search_results, reflection_round)
        update = await runtime.llm.generate_json(
            system, user, ReflectionUpdate,
            temperature=0.3,
            role=AgentRole.PROPOSER,
        )

        # Apply updates — only override if the reflection provided non-empty values
        if update.title:
            hypothesis.title = update.title
        if update.statement:
            hypothesis.statement = update.statement
        if update.description:
            hypothesis.description = update.description
        if update.related_work_summary:
            hypothesis.related_work_summary = update.related_work_summary
        if update.testable_prediction:
            hypothesis.testable_prediction = update.testable_prediction
        if update.risk_factors:
            # Merge, don't replace
            existing = set(hypothesis.risk_factors)
            for rf in update.risk_factors:
                if rf not in existing:
                    hypothesis.risk_factors.append(rf)
        if update.novelty_assessment and update.novelty_assessment.get("what_is_new"):
            from vreda_hypothesis.models import NoveltyAssessment
            existing_data = hypothesis.novelty_assessment.model_dump() if hasattr(hypothesis.novelty_assessment, 'model_dump') else dict(hypothesis.novelty_assessment)
            merged = {**existing_data, **update.novelty_assessment}
            hypothesis.novelty_assessment = NoveltyAssessment(**merged)

        hypothesis.reflection_rounds_completed += 1
        logger.debug(
            "refinement.reflection_complete",
            hypothesis=hypothesis.id,
            search_results=len(search_results),
        )
        return hypothesis

    except Exception as exc:
        logger.debug("refinement.reflection_failed", error=str(exc))
        return hypothesis  # On error, return unmodified


async def _critic_with_budget(
    critic: CriticAgent,
    hypothesis: EnhancedHypothesis,
    graph: PaperKnowledgeGraph,
    seed_score: ScoredSeed,
):
    budget_summary = f"Est. ${seed_score.budget_estimate_usd:.2f}, verifiability={seed_score.verifiability_score:.2f}"
    novelty_signal = graph.novelty_signal(hypothesis.description)
    assessment = await critic.review(hypothesis, novelty_signal, budget_summary)
    return assessment


def _build_context(state: PipelineState, meta_notes: list[str]) -> str:
    parts = []
    if state.paper_summary:
        parts.append(f"Abstract: {state.paper_summary.abstract[:600]}")
        parts.append(f"Methods: {', '.join(state.paper_summary.methods[:5])}")
        parts.append(f"Limitations: {', '.join(state.paper_summary.limitations[:5])}")
    if state.research_frame:
        parts.append(f"Core operators: {', '.join(state.research_frame.core_operators[:5])}")
        parts.append(f"Core mechanism: {state.research_frame.core_mechanism[:200]}")
    if state.meta_gaps:
        parts.append("Meta gaps: " + "; ".join(g.statement[:100] for g in state.meta_gaps[:3]))
    elif state.gap_analysis:
        parts.append("Known gaps: " + "; ".join(gap.title for gap in state.gap_analysis.gaps[:3]))
    if meta_notes:
        parts.append("Meta directives: " + "; ".join(meta_notes[-3:]))
    return "\n".join(parts)


def _gap_summary(state: PipelineState) -> str:
    if state.meta_gaps:
        return "; ".join(f"{g.gap_id}: {g.statement[:100]} ({g.gap_type})" for g in state.meta_gaps[:5])
    if state.gap_analysis:
        return "; ".join(f"{gap.title} ({gap.gap_type})" for gap in state.gap_analysis.gaps[:5])
    return ""


async def _quick_score_seed(runtime: PipelineRuntime, graph: PaperKnowledgeGraph, seed) -> ScoredSeed:
    """Score an evolved seed — uses LLM for verifiability (not hardcoded)."""
    from pydantic import BaseModel, Field

    class QuickVerify(BaseModel):
        verifiability: int = Field(ge=1, le=10)

    novelty_signal = graph.novelty_signal(seed.text)
    rag_hits = await runtime.vector_store.similarity_search(seed.text, k=1)
    sim = rag_hits[0]["score"] if rag_hits else 0.0
    novelty = max(0.0, 1.0 - max(sim, novelty_signal.overlap_ratio))

    from vreda_hypothesis.utils.cost import estimate_budget
    cost = estimate_budget(seed.text)

    from vreda_hypothesis.llm.prompts import verifiability_prompt
    system, user = verifiability_prompt(seed.text)
    verify_result = await runtime.llm.generate_json(
        system, user, QuickVerify,
        temperature=0.1,
        role=AgentRole.VERIFIABILITY,
    )
    verifiability_score = verify_result.verifiability / 10

    combined = novelty * 0.4 + verifiability_score * 0.3
    combined += (1.0 if cost["cost_with_contingency_usd"] < 20 else 0.3) * 0.3

    return ScoredSeed(
        seed=seed,
        novelty_score=novelty,
        budget_estimate_usd=cost["cost_with_contingency_usd"],
        verifiability_score=verifiability_score,
        combined_score=combined,
    )
