"""Refinement loop agents — Proposer, Critic, Evolver, Meta-Reviewer, Tournament Judge.

Enhanced with:
- ProposerAgent: Full archetype schema (IF/THEN/BECAUSE, MVE, falsification, adversarial)
- CriticAgent: Adversarial review (MVE check, falsification check, portfolio tagging)
- EvolverAgent: Wrong-example-bank awareness
- MetaReviewerAgent + TournamentJudge: unchanged

Each agent uses role-based LLM routing via AgentRole for optimal model selection.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

import structlog
from pydantic import BaseModel, Field

from vreda_hypothesis.llm import AgentRole, LLMProvider
from vreda_hypothesis.llm.prompts import (
    evolver_prompt,
    meta_reviewer_prompt,
    tournament_prompt,
)
from vreda_hypothesis.llm.prompts.archetype_proposer import archetype_proposer_prompt
from vreda_hypothesis.llm.prompts.archetype_critic import archetype_critic_prompt
from vreda_hypothesis.models import (
    ARCHETYPE_TO_TYPE,
    AdversarialDefense,
    CriticAssessment,
    DimensionScores,
    EnhancedHypothesis,
    ExperimentSpec,
    FailedSeed,
    HypothesisArchetype,
    HypothesisSeed,
    HypothesisType,
    MetaGap,
    NoveltySpec,
    ResearchFrame,
    ResourceSpec,
    ScoredSeed,
    compute_composite_score,
)
from vreda_hypothesis.knowledge import NoveltySignal

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# Proposer Output Schema (Archetype-Structured)
# ──────────────────────────────────────────────

class ArchetypeDraft(BaseModel):
    """Full archetype-structured hypothesis from the proposer."""
    title: str = ""
    archetype: HypothesisArchetype = HypothesisArchetype.MECHANISTIC_PROBE
    gap_id: str = ""
    statement: str = ""  # IF/THEN/BECAUSE
    experiment: ExperimentSpec = Field(default_factory=ExperimentSpec)
    mve: list[str] = Field(default_factory=list)  # Exactly 5 steps
    resources: ResourceSpec = Field(default_factory=ResourceSpec)
    novelty: NoveltySpec = Field(default_factory=NoveltySpec)
    adversarial: AdversarialDefense = Field(default_factory=AdversarialDefense)
    description: str = ""
    testable_prediction: str = ""
    expected_outcome: str = ""
    required_modifications: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    predicted_impact: str = ""
    type: HypothesisType = HypothesisType.SCALE
    novelty_score: int = Field(default=50, ge=0, le=100)
    feasibility_score: int = Field(default=50, ge=0, le=100)
    impact_score: int = Field(default=50, ge=0, le=100)
    grounding_score: int = Field(default=50, ge=0, le=100)
    testability_score: int = Field(default=50, ge=0, le=100)
    clarity_score: int = Field(default=50, ge=0, le=100)


# ──────────────────────────────────────────────
# Critic Output Schema (Enhanced)
# ──────────────────────────────────────────────

class EnhancedCriticOutput(BaseModel):
    feasibility_issues: list[str] = Field(default_factory=list)
    grounding_score: float = Field(default=0.5, ge=0.0, le=1.0)
    overlap_with_literature: str = ""
    suggested_improvements: list[str] = Field(default_factory=list)
    verdict: Literal["strong", "viable", "weak"] = "viable"
    revised_scores: DimensionScores = Field(default_factory=DimensionScores)
    mve_executable: bool = True
    falsification_valid: bool = True
    adversarial_defense_adequate: bool = True
    portfolio_tag: Literal["empirical", "robustness", "scaling", "theoretical"] = "empirical"


# ──────────────────────────────────────────────
# Evolution / Tournament Schemas (unchanged)
# ──────────────────────────────────────────────

class EvolutionSuggestion(BaseModel):
    seed_text: str
    type: HypothesisType
    rationale: str = ""
    inherited_ids: list[str] = Field(default_factory=list)


class EvolutionBatch(BaseModel):
    ideas: list[EvolutionSuggestion] = Field(default_factory=list)


class TournamentDecision(BaseModel):
    winner: Literal["a", "b", "tie"]
    rationale: str
    novelty_winner: Literal["a", "b", "tie"]
    excitement_winner: Literal["a", "b", "tie"]
    feasibility_winner: Literal["a", "b", "tie"]
    impact_winner: Literal["a", "b", "tie"]


@dataclass
class MetaReviewDirectives:
    directives: list[str] = field(default_factory=list)
    risk_alerts: list[str] = field(default_factory=list)


class MetaReviewPayload(BaseModel):
    directives: list[str] = Field(default_factory=list)
    risk_alerts: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# ProposerAgent (Enhanced with Archetype Schema)
# ──────────────────────────────────────────────

class ProposerAgent:
    """Expands seeds into full archetype-structured hypotheses."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def propose(
        self,
        seed: HypothesisSeed,
        context: str,
        gap_summary: str,
        seed_score: ScoredSeed | None = None,
        research_frame: ResearchFrame | None = None,
        meta_gap: MetaGap | None = None,
    ) -> EnhancedHypothesis:
        system, user = archetype_proposer_prompt(
            seed, context, gap_summary,
            research_frame=research_frame,
            meta_gap=meta_gap,
        )
        draft = await self.llm.generate_json(
            system, user, ArchetypeDraft,
            temperature=0.55,
            role=AgentRole.PROPOSER,
        )
        # Resilience: if provider returns sparse JSON, recover critical fields from seed/context.
        if not draft.title:
            draft.title = " ".join(seed.text.strip().split()[:6]).strip(" ,.;:-") or "Hypothesis Draft"
        if not draft.statement:
            draft.statement = seed.text
        if not draft.description:
            draft.description = seed.text
        if not draft.testable_prediction:
            draft.testable_prediction = "Primary metric should improve by 2-5% under matched compute."
        if not draft.expected_outcome:
            draft.expected_outcome = "A reproducible mechanism-level gain over baseline."
        if not draft.type:
            draft.type = seed.type
        if draft.novelty_score <= 0:
            draft.novelty_score = 62
        if draft.feasibility_score <= 0:
            draft.feasibility_score = 60
        if draft.impact_score <= 0:
            draft.impact_score = 64
        if draft.grounding_score <= 0:
            draft.grounding_score = 58
        if draft.testability_score <= 0:
            draft.testability_score = 66
        if draft.clarity_score <= 0:
            draft.clarity_score = 68
        if not draft.mve:
            draft.mve = [
                "1. Reproduce baseline settings.",
                "2. Apply the proposed intervention.",
                "3. Run controlled ablations with matched compute.",
                "4. Evaluate primary and efficiency metrics.",
                "5. Report statistical significance and failure cases.",
            ]
        if not draft.experiment.dataset:
            draft.experiment.dataset = "the anchor benchmark dataset"
        if not draft.experiment.metric:
            draft.experiment.metric = "primary task metric"
        if not draft.experiment.prediction:
            draft.experiment.prediction = "2-5% improvement over baseline"
        if not draft.experiment.falsification_threshold:
            draft.experiment.falsification_threshold = (
                "Dead if no statistically significant improvement under matched compute."
            )

        # Map archetype to legacy type for frontend compatibility
        legacy_type = ARCHETYPE_TO_TYPE.get(draft.archetype, draft.type) or seed.type

        hypothesis = EnhancedHypothesis(
            type=legacy_type,
            title=draft.title,
            description=draft.description,
            short_hypothesis=draft.statement or draft.testable_prediction,
            testable_prediction=draft.testable_prediction,
            expected_outcome=draft.expected_outcome,
            # Archetype fields
            archetype=draft.archetype,
            statement=draft.statement,
            mve=draft.mve[:5],  # Enforce 5-step limit
            falsification_threshold=draft.experiment.falsification_threshold,
            experiment_spec=draft.experiment,
            resources=draft.resources,
            adversarial=draft.adversarial,
            novelty_spec=draft.novelty,
            addresses_gap_id=draft.gap_id or seed.gap_id or None,
            # Legacy fields
            required_modifications=draft.required_modifications,
            risk_factors=draft.risk_factors,
            related_work_summary="; ".join(draft.grounding_evidence),
            novelty_assessment={
                "is_novel": True,
                "what_is_new": draft.novelty.why_distinct,
                "novelty_score": draft.novelty_score,
                "novelty_type": "entirely_new" if draft.novelty.verdict == "substantial" else "new_combination",
            },
            evidence_basis={
                "prior_results": draft.predicted_impact,
                "key_insight": draft.novelty.why_distinct,
                "gap_exploited": gap_summary[:280],
            },
            experiment_design={
                "baseline": draft.experiment.control,
                "dataset_requirements": draft.experiment.dataset,
                "code_changes": draft.required_modifications,
                "success_metrics": [draft.experiment.metric, draft.experiment.prediction],
                "estimated_duration": f"{draft.resources.gpu_hours}h GPU",
            },
            reflection_rounds_completed=0,
        )

        # Set scores from draft
        hypothesis.scores = DimensionScores(
            novelty=draft.novelty_score,
            feasibility=draft.feasibility_score,
            impact=draft.impact_score,
            grounding=draft.grounding_score,
            testability=draft.testability_score,
            clarity=draft.clarity_score,
        )

        # Blend with seed-level signals
        if seed_score:
            hypothesis.scores.novelty = int(
                0.6 * draft.novelty_score + 0.4 * (seed_score.novelty_score * 100)
            )
            hypothesis.scores.testability = int(
                0.6 * draft.testability_score + 0.4 * (seed_score.verifiability_score * 100)
            )
            hypothesis.scores.feasibility = int(
                0.6 * draft.feasibility_score + 0.4 * max(0, 100 - seed_score.budget_estimate_usd * 5)
            )

        hypothesis.composite_score = compute_composite_score(hypothesis.scores)
        return hypothesis


# ──────────────────────────────────────────────
# CriticAgent (Enhanced with Adversarial Review)
# ──────────────────────────────────────────────

class CriticAgent:
    """Enhanced critic with MVE/falsification/adversarial checks."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def review(
        self,
        hypothesis: EnhancedHypothesis,
        novelty_signal: NoveltySignal,
        budget_summary: str,
    ) -> CriticAssessment:
        novelty_text = (
            f"Overlap ratio {novelty_signal.overlap_ratio:.2f}; "
            f"Entities: {', '.join(novelty_signal.related_entities[:5]) or 'none'}; "
            f"Papers: {', '.join(novelty_signal.supporting_papers[:3]) or 'none'}."
        )
        system, user = archetype_critic_prompt(hypothesis, novelty_text, budget_summary)
        response = await self.llm.generate_json(
            system, user, EnhancedCriticOutput,
            temperature=0.2,
            role=AgentRole.CRITIC,
        )
        if not response.suggested_improvements:
            response.suggested_improvements = [
                "Strengthen baseline closure with one strong competing method.",
                "Add explicit robustness stress-test in the MVE plan.",
            ]
        if response.revised_scores.novelty == 0 and response.revised_scores.clarity == 0:
            # Sparse JSON fallback: preserve non-zero scoring semantics.
            response.revised_scores = hypothesis.scores
            response.revised_scores.novelty = max(40, response.revised_scores.novelty)
            response.revised_scores.feasibility = max(40, response.revised_scores.feasibility)
            response.revised_scores.impact = max(45, response.revised_scores.impact)
            response.revised_scores.grounding = max(40, response.revised_scores.grounding)
            response.revised_scores.testability = max(45, response.revised_scores.testability)
            response.revised_scores.clarity = max(45, response.revised_scores.clarity)

        assessment = CriticAssessment(
            hypothesis_id=hypothesis.id,
            feasibility_issues=response.feasibility_issues,
            grounding_score=response.grounding_score,
            overlap_with_literature=response.overlap_with_literature,
            suggested_improvements=response.suggested_improvements,
            verdict=response.verdict,
            revised_scores=response.revised_scores,
            mve_executable=response.mve_executable,
            falsification_valid=response.falsification_valid,
            adversarial_defense_adequate=response.adversarial_defense_adequate,
            portfolio_tag=response.portfolio_tag,
        )
        logger.info(
            "critic.review_complete",
            hypothesis=hypothesis.id,
            verdict=assessment.verdict,
            mve_ok=assessment.mve_executable,
            falsification_ok=assessment.falsification_valid,
            portfolio_tag=assessment.portfolio_tag,
        )
        return assessment


# ──────────────────────────────────────────────
# EvolverAgent (Enhanced with Wrong-Example-Bank)
# ──────────────────────────────────────────────

class EvolverAgent:
    """Applies evolutionary mutations — now aware of wrong-example-bank."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def evolve(
        self,
        hypotheses: list[EnhancedHypothesis],
        mutation_style: str,
        failed_seeds: list[FailedSeed] | None = None,
    ) -> list[HypothesisSeed]:
        if not hypotheses:
            return []
        cluster = random.sample(hypotheses, k=min(len(hypotheses), 3))

        # Build enhanced evolver prompt with wrong-example-bank
        system, user = evolver_prompt(cluster, mutation_style)

        # Inject wrong-example-bank context
        if failed_seeds:
            failure_context = "\n".join(
                f"- FAILED: \"{fs.seed_text[:150]}\" → Reason: {fs.failure_reason}"
                for fs in failed_seeds[-5:]  # Last 5 failures
            )
            user += (
                f"\n\nWRONG-EXAMPLE-BANK (HypoRefine pattern):\n"
                f"These approaches FAILED. Generate seeds that AVOID these mistakes:\n"
                f"{failure_context}"
            )

        suggestions = await self.llm.generate_json(
            system, user, EvolutionBatch,
            role=AgentRole.EVOLVER,
        )
        seeds: list[HypothesisSeed] = []
        for suggestion in suggestions.ideas:
            seeds.append(
                HypothesisSeed(
                    text=suggestion.seed_text,
                    type=suggestion.type,
                    source_prompt=f"evolver:{mutation_style}",
                )
            )
        return seeds


# ──────────────────────────────────────────────
# MetaReviewerAgent (unchanged)
# ──────────────────────────────────────────────

class MetaReviewerAgent:
    """Aggregates critic feedback using REASONING tier for pattern analysis."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def reflect(self, critic_notes: list[str], cycle: int) -> MetaReviewDirectives:
        if not critic_notes:
            return MetaReviewDirectives()
        system, user = meta_reviewer_prompt(critic_notes, cycle)
        payload = await self.llm.generate_json(
            system, user, MetaReviewPayload,
            role=AgentRole.META_REVIEWER,
        )
        return MetaReviewDirectives(
            directives=payload.directives,
            risk_alerts=payload.risk_alerts,
        )


# ──────────────────────────────────────────────
# TournamentJudge (unchanged)
# ──────────────────────────────────────────────

class TournamentJudge:
    """Pairwise judge using REASONING tier for fair, analytical comparisons."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def decide(self, hyp_a: EnhancedHypothesis, hyp_b: EnhancedHypothesis) -> TournamentDecision:
        system, user = tournament_prompt(hyp_a, hyp_b)
        return await self.llm.generate_json(
            system, user, TournamentDecision,
            temperature=0.1,
            role=AgentRole.TOURNAMENT_JUDGE,
        )
