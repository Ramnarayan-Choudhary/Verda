"""Pydantic models for the standalone GPT hypothesis engine."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class InputDocument(BaseModel):
    type: Literal["arxiv", "pdf", "text"] = "text"
    arxiv_id: str | None = None
    pdf_path: str | None = None
    text: str | None = None
    title: str | None = None


class PipelineConfig(BaseModel):
    top_k: int = Field(default=5, ge=1, le=10)
    tribunal_cycles: int = Field(default=2, ge=1, le=4)
    hypotheses_per_strategy: int = Field(default=3, ge=1, le=8)
    min_hypotheses_pool: int = Field(default=12, ge=6, le=80)


class Contradiction(BaseModel):
    claim: str
    paper_a: str
    paper_b: str
    nature: Literal["empirical", "theoretical", "scope"] = "scope"
    resolution_hypothesis: str = ""


class CrossDomainBridge(BaseModel):
    source_domain: str
    target_domain: str
    analogous_problem: str
    solved_by: str
    transfer_hypothesis: str


class AssumptionTarget(BaseModel):
    assumption: str
    held_by: list[str] = Field(default_factory=list)
    vulnerability_reason: str
    challenge_hypothesis: str


class PaperIntelligence(BaseModel):
    title: str
    domain: str = "other"
    subdomain: str = "general"
    year: int | None = None
    central_claim: str = ""
    core_mechanism: str = ""
    key_assumptions: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    empirical_results: list[str] = Field(default_factory=list)
    explicit_limitations: list[str] = Field(default_factory=list)
    implicit_limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    missing_baselines: list[str] = Field(default_factory=list)
    untested_conditions: list[str] = Field(default_factory=list)
    analogous_domains: list[str] = Field(default_factory=list)
    borrowed_concepts: list[str] = Field(default_factory=list)
    exportable_concepts: list[str] = Field(default_factory=list)
    confidence_level: Literal["preliminary", "established", "contested"] = "preliminary"
    replication_status: Literal["replicated", "single_study", "contested"] = "single_study"
    contradicted_by: list[str] = Field(default_factory=list)


class ResearchLandscape(BaseModel):
    research_intent: str
    intent_domain: str = "other"
    intent_subdomain: str = "general"
    shared_assumptions: list[str] = Field(default_factory=list)
    contested_claims: list[Contradiction] = Field(default_factory=list)
    methodological_consensus: list[str] = Field(default_factory=list)
    dominant_paradigm: str = ""
    established_facts: list[str] = Field(default_factory=list)
    open_problems: list[str] = Field(default_factory=list)
    pseudoknowledge: list[str] = Field(default_factory=list)
    cross_domain_opportunities: list[CrossDomainBridge] = Field(default_factory=list)
    assumption_vulnerabilities: list[AssumptionTarget] = Field(default_factory=list)
    methodological_gaps: list[str] = Field(default_factory=list)
    theoretical_upper_bound: str | None = None
    bottleneck_hypothesis: str = ""


class GapAnalysis(BaseModel):
    gap_id: str = Field(default_factory=lambda: f"G{uuid.uuid4().hex[:6].upper()}")
    gap_type: Literal["knowledge", "method", "assumption", "theoretical"]
    statement: str
    why_it_matters: str
    expected_impact: Literal["low", "medium", "high", "paradigm_shift"] = "medium"
    nearest_prior_work: str = ""
    difficulty_estimate: Literal["well-defined", "complex", "open"] = "complex"
    source_papers: list[str] = Field(default_factory=list)
    cross_domain_hint: str | None = None


class ResearchSpaceMap(BaseModel):
    knowledge_gaps: list[GapAnalysis] = Field(default_factory=list)
    method_gaps: list[GapAnalysis] = Field(default_factory=list)
    assumption_gaps: list[GapAnalysis] = Field(default_factory=list)
    theoretical_gaps: list[GapAnalysis] = Field(default_factory=list)
    high_value_targets: list[str] = Field(default_factory=list)


class MinimalTest(BaseModel):
    dataset: str
    baseline: str
    primary_metric: str
    success_threshold: str
    estimated_compute: str
    estimated_timeline: str


class StructuredHypothesis(BaseModel):
    id: str = Field(default_factory=lambda: f"hyp-{uuid.uuid4().hex[:8]}")
    generation_strategy: str
    source_gap_id: str
    title: str
    condition: str
    intervention: str
    prediction: str
    mechanism: str
    falsification_criterion: str
    minimum_viable_test: MinimalTest
    closest_existing_work: str
    novelty_claim: str
    expected_outcome_if_true: str
    expected_outcome_if_false: str
    theoretical_basis: str


class DomainCritique(BaseModel):
    is_physically_possible: bool = True
    violates_known_principles: list[str] = Field(default_factory=list)
    domain_validity_score: float = Field(default=0.7, ge=0.0, le=1.0)
    specific_concerns: str = ""


class MethodologyCritique(BaseModel):
    experiment_is_valid: bool = True
    confounds_identified: list[str] = Field(default_factory=list)
    control_issues: list[str] = Field(default_factory=list)
    metric_concerns: str = ""
    suggested_redesign: str | None = None


class DevilsAdvocate(BaseModel):
    strongest_objection: str = ""
    counter_evidence: str = ""
    null_hypothesis: str = ""
    rebuttal_possibility: str = ""


class ResourceCritique(BaseModel):
    compute_realistic: bool = True
    data_available: bool = True
    timeline_estimate: str = "2-4 weeks"
    blocking_conditions: list[str] = Field(default_factory=list)
    feasibility_score: float = Field(default=0.75, ge=0.0, le=1.0)


class MechanismValidation(BaseModel):
    causal_chain_complete: bool = True
    identified_gaps: list[str] = Field(default_factory=list)
    strengthened_mechanism: str = ""
    logical_score: float = Field(default=0.7, ge=0.0, le=1.0)


class TribunalVerdict(BaseModel):
    hypothesis_id: str
    domain_validity: DomainCritique
    methodology: MethodologyCritique
    devils_advocate: DevilsAdvocate
    resource_reality: ResourceCritique
    mechanism_validation: MechanismValidation
    overall_verdict: Literal["advance", "revise", "abandon"] = "revise"
    primary_weakness: str = ""
    revision_directive: str = ""


class DimensionScores(BaseModel):
    mechanistic_quality: float = Field(default=0.0, ge=0.0, le=10.0)
    novelty: float = Field(default=0.0, ge=0.0, le=10.0)
    testability: float = Field(default=0.0, ge=0.0, le=10.0)
    scientific_impact: float = Field(default=0.0, ge=0.0, le=10.0)
    feasibility: float = Field(default=0.0, ge=0.0, le=10.0)
    specificity: float = Field(default=0.0, ge=0.0, le=10.0)
    creativity: float = Field(default=0.0, ge=0.0, le=10.0)


class PortfolioHypothesis(BaseModel):
    hypothesis: StructuredHypothesis
    portfolio_slot: Literal["safe", "medium", "moonshot"]
    dimension_scores: DimensionScores
    tribunal_verdict: TribunalVerdict
    portfolio_position_rationale: str
    suggested_timeline: str
    dependencies: list[str] = Field(default_factory=list)
    success_definition: str
    failure_learning: str


class ResourceSummary(BaseModel):
    estimated_compute_hours: float = 0.0
    timeline_summary: str = ""
    data_dependencies: list[str] = Field(default_factory=list)


class ResearchPortfolio(BaseModel):
    hypotheses: list[PortfolioHypothesis] = Field(default_factory=list)
    portfolio_rationale: str = ""
    suggested_execution_order: list[str] = Field(default_factory=list)
    resource_summary: ResourceSummary = Field(default_factory=ResourceSummary)


class LegacyDimensionScores(BaseModel):
    novelty: int = Field(default=50, ge=0, le=100)
    feasibility: int = Field(default=50, ge=0, le=100)
    impact: int = Field(default=50, ge=0, le=100)
    grounding: int = Field(default=50, ge=0, le=100)
    testability: int = Field(default=50, ge=0, le=100)
    clarity: int = Field(default=50, ge=0, le=100)


class LegacyHypothesis(BaseModel):
    id: str
    type: str = "combination"
    title: str
    description: str
    short_hypothesis: str
    testable_prediction: str
    expected_outcome: str
    scores: LegacyDimensionScores
    composite_score: int
    required_modifications: list[str] = Field(default_factory=list)
    estimated_complexity: Literal["low", "medium", "high"] = "medium"
    evidence_basis: dict = Field(default_factory=dict)
    novelty_assessment: dict = Field(default_factory=dict)
    experiment_design: dict = Field(default_factory=dict)
    risk_factors: list[str] = Field(default_factory=list)
    related_work_summary: str = ""
    addresses_gap_id: str | None = None
    critic_assessment: dict | None = None
    reflection_rounds_completed: int = 0
    archetype: str = "mechanistic_probe"
    statement: str = ""
    mve: list[str] = Field(default_factory=list)
    falsification_threshold: str = ""
    portfolio_tag: str = "empirical"
    elo_rating: float = 1500.0


class GeneratorOutput(BaseModel):
    hypotheses: list[LegacyHypothesis] = Field(default_factory=list)
    reasoning_context: str = ""
    gap_analysis_used: bool = True
    reflection_rounds: int = 0
    generation_strategy: Literal["knowledge_grounded", "prompt_based"] = "knowledge_grounded"
    portfolio_audit: dict | None = None
    engine_used: Literal["gpt"] = "gpt"
    diagnostics: dict = Field(default_factory=dict)


class ProgressEvent(BaseModel):
    type: Literal["progress", "warning", "complete", "error"]
    step: str | None = None
    message: str
    current: int | None = None
    total: int | None = None
    data: dict | None = None


class GenerateRequest(BaseModel):
    arxiv_id: str | None = None
    pdf_path: str | None = None
    research_intent: str | None = None
    input_documents: list[InputDocument] | None = None
    config: PipelineConfig = Field(default_factory=PipelineConfig)


class PipelineState(BaseModel):
    research_intent: str
    input_documents: list[InputDocument]
    config: PipelineConfig
    paper_intelligences: list[PaperIntelligence] = Field(default_factory=list)
    research_landscape: ResearchLandscape | None = None
    research_space_map: ResearchSpaceMap | None = None
    strategy_outputs: dict[str, list[StructuredHypothesis]] = Field(default_factory=dict)
    hypothesis_pool: list[StructuredHypothesis] = Field(default_factory=list)
    tribunal_verdicts: dict[str, TribunalVerdict] = Field(default_factory=dict)
    refined_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)
    dimension_scores: dict[str, DimensionScores] = Field(default_factory=dict)
    ranked_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)
    final_portfolio: ResearchPortfolio | None = None
    refinement_cycle: int = 0
    errors: list[str] = Field(default_factory=list)
