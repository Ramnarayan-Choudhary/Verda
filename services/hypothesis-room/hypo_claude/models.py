"""
Pydantic models for the 6-layer Epistemic Engine hypothesis pipeline.

Layer 0: Multi-Document Intelligence (PaperIntelligence, ResearchLandscape)
Layer 1: Research Space Cartography (GapAnalysis, ResearchSpaceMap)
Layer 2: Multi-Strategy Generation (StructuredHypothesis, MinimalTest)
Layer 3: Adversarial Tribunal (TribunalVerdict, 4 critique models)
Layer 4: Panel Evaluation (DimensionScores, JudgeScore)
Layer 5: Portfolio Construction (ResearchPortfolio, PortfolioHypothesis)
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ── Helpers ──────────────────────────────────────────────────────────

def _gen_id(prefix: str = "id") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ═══════════════════════════════════════════════════════════════════════
# LAYER 0 — Multi-Document Intelligence
# ═══════════════════════════════════════════════════════════════════════

class PaperIntelligence(BaseModel):
    """Deep structured extraction from a single research paper."""
    paper_id: str = Field(default_factory=lambda: _gen_id("paper"))
    title: str = ""
    domain: str = ""
    subdomain: str = ""
    year: int | None = None

    # Core scientific content
    central_claim: str = ""
    core_mechanism: str = ""
    key_assumptions: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    empirical_results: list[str] = Field(default_factory=list)

    # Limitations — where hypotheses come from
    explicit_limitations: list[str] = Field(default_factory=list)
    implicit_limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    missing_baselines: list[str] = Field(default_factory=list)
    untested_conditions: list[str] = Field(default_factory=list)

    # Cross-domain signals
    analogous_domains: list[str] = Field(default_factory=list)
    borrowed_concepts: list[str] = Field(default_factory=list)
    exportable_concepts: list[str] = Field(default_factory=list)

    # Epistemic status
    confidence_level: Literal["preliminary", "established", "contested"] = "preliminary"
    replication_status: Literal["replicated", "single_study", "contested"] = "single_study"
    contradicted_by: list[str] = Field(default_factory=list)

    @field_validator("key_assumptions", "methods", "empirical_results",
                     "explicit_limitations", "implicit_limitations", "open_questions",
                     "missing_baselines", "untested_conditions", "analogous_domains",
                     "borrowed_concepts", "exportable_concepts", "contradicted_by",
                     mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []


class Contradiction(BaseModel):
    """Where two papers disagree."""
    claim: str = ""
    paper_a: str = ""
    paper_b: str = ""
    nature: Literal["empirical", "theoretical", "scope"] = "empirical"
    resolution_hypothesis: str = ""


class CrossDomainBridge(BaseModel):
    """A solved problem in another domain that might transfer."""
    source_domain: str = ""
    target_domain: str = ""
    analogous_problem: str = ""
    solved_by: str = ""
    transfer_hypothesis: str = ""


class AssumptionTarget(BaseModel):
    """A shared assumption that might be wrong."""
    assumption: str = ""
    held_by: list[str] = Field(default_factory=list)
    vulnerability_reason: str = ""
    challenge_hypothesis: str = ""


class ResearchLandscape(BaseModel):
    """Cross-document synthesis — the unified intelligence object."""
    research_intent: str = ""
    intent_domain: str = ""
    intent_subdomain: str = ""

    # Landscape mapping
    shared_assumptions: list[str] = Field(default_factory=list)
    contested_claims: list[Contradiction] = Field(default_factory=list)
    methodological_consensus: list[str] = Field(default_factory=list)
    dominant_paradigm: str = ""

    # Knowledge state
    established_facts: list[str] = Field(default_factory=list)
    open_problems: list[str] = Field(default_factory=list)
    pseudoknowledge: list[str] = Field(default_factory=list)

    # Opportunity signals
    cross_domain_opportunities: list[CrossDomainBridge] = Field(default_factory=list)
    assumption_vulnerabilities: list[AssumptionTarget] = Field(default_factory=list)
    methodological_gaps: list[str] = Field(default_factory=list)

    # Frontier
    theoretical_upper_bound: str | None = None
    bottleneck_hypothesis: str = ""


# ═══════════════════════════════════════════════════════════════════════
# LAYER 1 — Research Space Cartography
# ═══════════════════════════════════════════════════════════════════════

class GapAnalysis(BaseModel):
    """A research gap with 4-type taxonomy."""
    gap_id: str = Field(default_factory=lambda: _gen_id("gap"))
    gap_type: Literal["knowledge", "method", "assumption", "theoretical"] = "knowledge"
    statement: str = ""
    why_it_matters: str = ""
    expected_impact: Literal["low", "medium", "high", "paradigm_shift"] = "medium"
    nearest_prior_work: str = ""
    difficulty_estimate: Literal["well-defined", "complex", "open"] = "complex"
    source_papers: list[str] = Field(default_factory=list)
    cross_domain_hint: str | None = None


class ResearchSpaceMap(BaseModel):
    """Cartography output — the 4-type gap taxonomy."""
    knowledge_gaps: list[GapAnalysis] = Field(default_factory=list)
    method_gaps: list[GapAnalysis] = Field(default_factory=list)
    assumption_gaps: list[GapAnalysis] = Field(default_factory=list)
    theoretical_gaps: list[GapAnalysis] = Field(default_factory=list)
    high_value_targets: list[str] = Field(
        default_factory=list,
        description="Top 5-7 gap_ids by combined value",
    )

    @property
    def all_gaps(self) -> list[GapAnalysis]:
        return self.knowledge_gaps + self.method_gaps + self.assumption_gaps + self.theoretical_gaps

    def get_gap(self, gap_id: str) -> GapAnalysis | None:
        for gap in self.all_gaps:
            if gap.gap_id == gap_id:
                return gap
        return None


# ═══════════════════════════════════════════════════════════════════════
# LAYER 2 — Multi-Strategy Hypothesis Generation
# ═══════════════════════════════════════════════════════════════════════

GENERATION_STRATEGIES = [
    "assumption_challenger",
    "domain_bridge",
    "contradiction_resolver",
    "constraint_relaxer",
    "mechanism_extractor",
    "synthesis_catalyst",
    "falsification_designer",
]


class MinimalTest(BaseModel):
    """Minimum viable experiment specification."""
    dataset: str = ""
    baseline: str = ""
    primary_metric: str = ""
    success_threshold: str = ""
    estimated_compute: str = ""
    estimated_timeline: str = ""


class StructuredHypothesis(BaseModel):
    """A hypothesis with full causal chain — output of all 7 strategies."""
    id: str = Field(default_factory=lambda: _gen_id("hyp"))
    generation_strategy: str = ""
    source_gap_id: str = ""

    # Core scientific content
    title: str = ""

    # The formal claim — ALL 4 components required
    condition: str = ""
    intervention: str = ""
    prediction: str = ""
    mechanism: str = ""

    # Testability
    falsification_criterion: str = ""
    minimal_test: MinimalTest = Field(default_factory=MinimalTest)

    # Novelty
    closest_existing_work: str = ""
    novelty_claim: str = ""

    # Confidence calibration
    expected_outcome_if_true: str = ""
    expected_outcome_if_false: str = ""
    theoretical_basis: str = ""


# ═══════════════════════════════════════════════════════════════════════
# LAYER 3 — Adversarial Tribunal
# ═══════════════════════════════════════════════════════════════════════

class DomainCritique(BaseModel):
    """Does this violate known scientific principles?"""
    is_physically_possible: bool = True
    violates_known_principles: list[str] = Field(default_factory=list)
    domain_validity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    specific_concerns: str = ""


class MethodologyCritique(BaseModel):
    """Is the proposed experiment actually valid?"""
    experiment_is_valid: bool = True
    confounds_identified: list[str] = Field(default_factory=list)
    control_issues: list[str] = Field(default_factory=list)
    metric_concerns: str = ""
    suggested_redesign: str | None = None


class DevilsAdvocateCritique(BaseModel):
    """The strongest case AGAINST this hypothesis."""
    strongest_objection: str = ""
    counter_evidence: str = ""
    null_hypothesis: str = ""
    rebuttal_possibility: str = ""


class ResourceCritique(BaseModel):
    """Can this actually be done?"""
    compute_realistic: bool = True
    data_available: bool = True
    timeline_estimate: str = ""
    blocking_conditions: list[str] = Field(default_factory=list)
    feasibility_score: float = Field(default=0.5, ge=0.0, le=1.0)


class MechanismValidation(BaseModel):
    """Logical consistency check on the causal chain."""
    causal_chain_complete: bool = True
    identified_gaps: list[str] = Field(default_factory=list)
    strengthened_mechanism: str = ""
    logical_score: float = Field(default=0.5, ge=0.0, le=1.0)


class TribunalVerdict(BaseModel):
    """Aggregated verdict from all 4 critics + mechanism validator."""
    hypothesis_id: str = ""

    domain_validity: DomainCritique = Field(default_factory=DomainCritique)
    methodology: MethodologyCritique = Field(default_factory=MethodologyCritique)
    devils_advocate: DevilsAdvocateCritique = Field(default_factory=DevilsAdvocateCritique)
    resource_reality: ResourceCritique = Field(default_factory=ResourceCritique)
    mechanism_validation: MechanismValidation = Field(default_factory=MechanismValidation)

    # Synthesis
    overall_verdict: Literal["advance", "revise", "abandon"] = "revise"
    primary_weakness: str = ""
    revision_directive: str = ""


# Mutation strategies for the Evolver
MUTATION_STRATEGIES = {
    "scope_reduction": "Narrow the claim to the specific sub-case where the mechanism definitely holds",
    "mechanism_deepening": "Add one more level of causal detail between cause and effect",
    "prediction_sharpening": "Replace qualitative with quantitative predictions, add error bounds",
    "condition_specification": "Specify exact conditions under which hypothesis holds vs breaks",
    "baseline_anchoring": "Add a specific named comparison baseline and numeric threshold",
}


# ═══════════════════════════════════════════════════════════════════════
# LAYER 4 — Multi-Dimensional Evaluation
# ═══════════════════════════════════════════════════════════════════════

DIMENSION_WEIGHTS = {
    "mechanistic_quality": 0.25,
    "novelty": 0.20,
    "testability": 0.20,
    "impact": 0.15,
    "feasibility": 0.10,
    "specificity": 0.05,
    "creativity": 0.05,
}


class DimensionScores(BaseModel):
    """7-axis scoring — each 0-100."""
    mechanistic_quality: int = Field(default=0, ge=0, le=100)
    novelty: int = Field(default=0, ge=0, le=100)
    testability: int = Field(default=0, ge=0, le=100)
    impact: int = Field(default=0, ge=0, le=100)
    feasibility: int = Field(default=0, ge=0, le=100)
    specificity: int = Field(default=0, ge=0, le=100)
    creativity: int = Field(default=0, ge=0, le=100)

    @property
    def composite(self) -> float:
        total = 0.0
        for dim, weight in DIMENSION_WEIGHTS.items():
            total += getattr(self, dim, 0) * weight
        return round(total, 1)


class JudgeScore(BaseModel):
    """One judge's evaluation of one hypothesis."""
    judge_persona: Literal["conservative", "generalist", "practitioner"] = "conservative"
    scores: DimensionScores = Field(default_factory=DimensionScores)
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


JUDGE_WEIGHTS = {
    "conservative": 0.35,
    "generalist": 0.30,
    "practitioner": 0.35,
}


def compute_panel_composite(judge_scores: list[JudgeScore]) -> float:
    """Weighted average composite across panel judges."""
    if not judge_scores:
        return 0.0
    total = 0.0
    weight_sum = 0.0
    for js in judge_scores:
        w = JUDGE_WEIGHTS.get(js.judge_persona, 0.33)
        total += js.scores.composite * w
        weight_sum += w
    return round(total / weight_sum, 1) if weight_sum > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════
# LAYER 5 — Strategic Portfolio Construction
# ═══════════════════════════════════════════════════════════════════════

class PortfolioHypothesis(BaseModel):
    """A hypothesis with its slot assignment and full evaluation context."""
    hypothesis: StructuredHypothesis = Field(default_factory=StructuredHypothesis)
    portfolio_slot: Literal["safe", "medium", "moonshot"] = "medium"
    dimension_scores: DimensionScores = Field(default_factory=DimensionScores)
    tribunal_verdict: TribunalVerdict = Field(default_factory=TribunalVerdict)
    panel_composite: float = 0.0
    suggested_timeline: str = ""
    dependencies: list[str] = Field(default_factory=list)
    success_definition: str = ""
    failure_learning: str = ""


class ResourceSummary(BaseModel):
    """Aggregate resource needs for the portfolio."""
    total_gpu_hours: int = 0
    total_cost_usd: float = 0.0
    critical_datasets: list[str] = Field(default_factory=list)
    critical_compute: str = ""


class ResearchPortfolio(BaseModel):
    """The final output — 4-5 strategically selected hypotheses."""
    hypotheses: list[PortfolioHypothesis] = Field(default_factory=list)
    portfolio_rationale: str = ""
    suggested_execution_order: list[str] = Field(default_factory=list)
    resource_summary: ResourceSummary = Field(default_factory=ResourceSummary)

    @property
    def safe_hypotheses(self) -> list[PortfolioHypothesis]:
        return [h for h in self.hypotheses if h.portfolio_slot == "safe"]

    @property
    def medium_hypotheses(self) -> list[PortfolioHypothesis]:
        return [h for h in self.hypotheses if h.portfolio_slot == "medium"]

    @property
    def moonshot_hypotheses(self) -> list[PortfolioHypothesis]:
        return [h for h in self.hypotheses if h.portfolio_slot == "moonshot"]


# ═══════════════════════════════════════════════════════════════════════
# Pipeline Infrastructure
# ═══════════════════════════════════════════════════════════════════════

class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add(self, prompt: int, completion: int, cost: float = 0.0) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion
        self.estimated_cost_usd += cost


class StageError(BaseModel):
    stage: str
    message: str
    recoverable: bool = True


class PipelineConfig(BaseModel):
    """User-configurable pipeline parameters."""
    max_hypotheses_per_strategy: int = Field(default=5, ge=2, le=10)
    tribunal_cycles: int = Field(default=3, ge=1, le=5)
    portfolio_safe_slots: int = Field(default=2, ge=1, le=3)
    portfolio_medium_slots: int = Field(default=2, ge=1, le=3)
    portfolio_moonshot_slots: int = Field(default=1, ge=0, le=2)
    dedup_threshold: float = Field(default=0.80, ge=0.5, le=1.0)
    domain: str = "other"
    stage_timeouts: dict[str, int] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class PipelineState(BaseModel):
    """Central state for the LangGraph pipeline."""
    # Input
    arxiv_id: str | None = None
    pdf_path: str | None = None
    arxiv_ids: list[str] = Field(default_factory=list)
    config: PipelineConfig = Field(default_factory=PipelineConfig)

    # Layer 0: Intelligence
    paper_intelligences: list[PaperIntelligence] = Field(default_factory=list)
    research_landscape: ResearchLandscape | None = None
    text_chunks: list[str] = Field(default_factory=list)

    # Layer 1: Cartography
    research_space_map: ResearchSpaceMap | None = None
    related_papers: list[dict] = Field(default_factory=list)

    # Layer 2: Generation
    strategy_outputs: dict[str, list[StructuredHypothesis]] = Field(default_factory=dict)
    hypothesis_pool: list[StructuredHypothesis] = Field(default_factory=list)

    # Layer 3: Tribunal
    tribunal_verdicts: dict[str, TribunalVerdict] = Field(default_factory=dict)
    refined_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)
    refinement_cycle: int = 0

    # Layer 4: Evaluation
    panel_scores: dict[str, list[JudgeScore]] = Field(default_factory=dict)
    ranked_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)

    # Layer 5: Portfolio
    research_portfolio: ResearchPortfolio | None = None

    # Output
    final_output: GeneratorOutput | None = None

    # Infra
    vector_store: Any = None
    progress_callback: Any = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    errors: list[StageError] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


class GenerateRequest(BaseModel):
    """FastAPI request body for /generate."""
    arxiv_id: str | None = None
    pdf_path: str | None = None
    arxiv_ids: list[str] = Field(default_factory=list)
    config: PipelineConfig = Field(default_factory=PipelineConfig)


class ProgressEvent(BaseModel):
    """NDJSON progress event."""
    type: Literal["progress", "warning", "complete", "error"]
    step: str | None = None
    message: str
    current: int | None = None
    total: int | None = None
    data: dict[str, Any] | None = None


class GeneratorOutput(BaseModel):
    """Final API output — backward-compatible with TS frontend."""
    hypotheses: list[dict] = Field(default_factory=list)
    reasoning_context: str = ""
    gap_analysis_used: bool = False
    reflection_rounds: int = 0
    generation_strategy: str = "epistemic_engine"
    research_portfolio: ResearchPortfolio | None = None
    pipeline_version: str = "v2"
