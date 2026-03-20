"""Pydantic models for the standalone GPT hypothesis engine."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    pipeline_version: Literal["v1", "v2"] = "v2"
    output_schema: Literal["legacy", "v2"] = "legacy"
    risk_appetite: Literal["conservative", "balanced", "moonshot"] = "balanced"
    max_rounds: int = Field(default=4, ge=1, le=8)
    enable_memory: bool = True
    enable_external_search: bool = True
    domain_hint: str | None = None


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
    contestable_assumptions: list[AssumptionTarget] = Field(default_factory=list)
    cross_domain_bridges: list[CrossDomainBridge] = Field(default_factory=list)
    sota_ceiling_statement: str = ""
    sota_structural_reason: str = ""
    sota_break_condition: str = ""
    failed_approaches_analysis: list[str] = Field(default_factory=list)
    evidence_density: float = Field(default=0.5, ge=0.0, le=1.0)


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


class CausalChain(BaseModel):
    intervention: str
    intermediate: str
    outcome: str
    conditions: list[str] = Field(default_factory=list)
    breaks_when: list[str] = Field(default_factory=list)

    @field_validator("intervention", "intermediate", "outcome")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("causal chain fields cannot be empty")
        return value

    @field_validator("intermediate")
    @classmethod
    def intermediate_min_words(cls, value: str) -> str:
        if len(value.split()) < 15:
            raise ValueError("causal_chain.intermediate must be at least 15 words")
        return value


class ExperimentSketch(BaseModel):
    design: str
    baseline: str
    primary_metric: str
    success_threshold: str
    compute_estimate: str
    time_horizon: Literal["1_month", "3_months", "6_months", "12months_plus"]
    required_data: str


class HypothesisV2(BaseModel):
    hypo_id: str = Field(default_factory=lambda: f"hyp2-{uuid.uuid4().hex[:8]}")
    title: str = Field(max_length=120)
    strategy: Literal[
        "gap_fill",
        "cross_domain",
        "assumption_challenge",
        "method_recomb",
        "failure_inversion",
        "abductive",
        "constraint_relax",
    ]
    problem_being_solved: str
    core_claim: str
    causal_chain: CausalChain
    falsification_criterion: str
    grounding_paper_ids: list[str]
    challenged_assumption: str | None = None
    source_domain_bridge: str | None = None
    anomaly_being_explained: str | None = None
    experiment: ExperimentSketch
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    feasibility: float = Field(default=0.0, ge=0.0, le=1.0)
    mechanism_coherence: float = Field(default=0.0, ge=0.0, le=1.0)
    executability: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tree_node_id: str = ""
    parent_hypo_ids: list[str] = Field(default_factory=list)
    mutation_operator: str = "none"
    generation_round: int = 0

    @field_validator("grounding_paper_ids")
    @classmethod
    def min_citations(cls, value: list[str]) -> list[str]:
        if len(value) < 2:
            raise ValueError("Every hypothesis must cite >= 2 papers from landscape")
        return value

    @field_validator("falsification_criterion")
    @classmethod
    def specific_falsification(cls, value: str) -> str:
        lowered = value.lower()
        vague = ["might", "may", "could", "suggest"]
        if any(token in lowered for token in vague):
            raise ValueError("falsification_criterion is too vague")
        if not any(char.isdigit() for char in value):
            raise ValueError("falsification_criterion must include a numeric threshold")
        if "<" not in value and ">" not in value and "below" not in lowered and "above" not in lowered:
            raise ValueError("falsification_criterion must include a comparison direction")
        return value

    @classmethod
    def from_structured(cls, hypothesis: StructuredHypothesis) -> "HypothesisV2":
        return cls(
            title=hypothesis.title[:120],
            strategy=_legacy_strategy_to_v2(hypothesis.generation_strategy),
            problem_being_solved=hypothesis.condition,
            core_claim=hypothesis.intervention,
            causal_chain=CausalChain(
                intervention=hypothesis.intervention,
                intermediate=f"{hypothesis.mechanism} Measured using explicit mediator readouts and controlled ablations.",
                outcome=hypothesis.prediction,
                conditions=[hypothesis.condition],
                breaks_when=["effect disappears in equal-compute ablation"],
            ),
            falsification_criterion=_ensure_numeric_falsification(hypothesis.falsification_criterion),
            grounding_paper_ids=["paper_1", "paper_2"],
            experiment=ExperimentSketch(
                design=hypothesis.minimum_viable_test.dataset,
                baseline=hypothesis.minimum_viable_test.baseline,
                primary_metric=hypothesis.minimum_viable_test.primary_metric,
                success_threshold=hypothesis.minimum_viable_test.success_threshold,
                compute_estimate=hypothesis.minimum_viable_test.estimated_compute,
                time_horizon=_timeline_to_horizon(hypothesis.minimum_viable_test.estimated_timeline),
                required_data=hypothesis.minimum_viable_test.dataset,
            ),
        )

    def to_structured(self) -> StructuredHypothesis:
        return StructuredHypothesis(
            id=_structured_id_from_hypo(self.hypo_id),
            generation_strategy=_v2_strategy_to_legacy(self.strategy),
            source_gap_id=(self.grounding_paper_ids[0] if self.grounding_paper_ids else "G0000"),
            title=self.title,
            condition=self.problem_being_solved,
            intervention=self.core_claim,
            prediction=self.causal_chain.outcome,
            mechanism=self.causal_chain.intermediate,
            falsification_criterion=self.falsification_criterion,
            minimum_viable_test=MinimalTest(
                dataset=self.experiment.required_data,
                baseline=self.experiment.baseline,
                primary_metric=self.experiment.primary_metric,
                success_threshold=self.experiment.success_threshold,
                estimated_compute=self.experiment.compute_estimate,
                estimated_timeline=_horizon_to_timeline(self.experiment.time_horizon),
            ),
            closest_existing_work=", ".join(self.grounding_paper_ids[:2]),
            novelty_claim=f"Composite novelty score: {self.novelty:.2f}",
            expected_outcome_if_true=self.causal_chain.outcome,
            expected_outcome_if_false="Mechanism likely invalid or non-causal.",
            theoretical_basis=self.problem_being_solved,
        )


def _legacy_strategy_to_v2(strategy: str) -> str:
    mapping = {
        "assumption_challenger": "assumption_challenge",
        "domain_bridge": "cross_domain",
        "contradiction_resolver": "abductive",
        "constraint_relaxer": "constraint_relax",
        "mechanism_extractor": "gap_fill",
        "synthesis_catalyst": "method_recomb",
        "falsification_designer": "failure_inversion",
    }
    return mapping.get(strategy, "gap_fill")


def _v2_strategy_to_legacy(strategy: str) -> str:
    mapping = {
        "assumption_challenge": "assumption_challenger",
        "cross_domain": "domain_bridge",
        "abductive": "contradiction_resolver",
        "constraint_relax": "constraint_relaxer",
        "gap_fill": "mechanism_extractor",
        "method_recomb": "synthesis_catalyst",
        "failure_inversion": "falsification_designer",
    }
    return mapping.get(strategy, "synthesis_catalyst")


def _timeline_to_horizon(timeline: str) -> Literal["1_month", "3_months", "6_months", "12months_plus"]:
    lower = timeline.lower()
    if "1" in lower and "month" in lower:
        return "1_month"
    if "6" in lower:
        return "6_months"
    if "12" in lower or "year" in lower:
        return "12months_plus"
    return "3_months"


def _horizon_to_timeline(horizon: str) -> str:
    mapping = {
        "1_month": "1 month",
        "3_months": "3 months",
        "6_months": "6 months",
        "12months_plus": "12+ months",
    }
    return mapping.get(horizon, "3 months")


def _ensure_numeric_falsification(value: str) -> str:
    if any(char.isdigit() for char in value):
        return value
    return f"{value} Fail if primary metric is < 1.0 under controlled condition."


def _structured_id_from_hypo(hypo_id: str) -> str:
    if hypo_id.startswith("hyp2-"):
        return f"hyp-{hypo_id[5:]}"
    if hypo_id.startswith("hyp-"):
        return hypo_id
    return f"hyp-{hypo_id[-8:]}"


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


class IdeaTreeNode(BaseModel):
    node_id: str
    hypothesis: HypothesisV2
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    mutation_operator: str = "none"
    embedding: list[float] = Field(default_factory=list)
    visit_count: int = 0
    total_value: float = 0.0
    is_pruned: bool = False
    metric_delta: float | None = None

    def ucb_score(self, total_visits: int, c: float = 1.41, novelty_bonus: float = 0.0) -> float:
        if self.visit_count == 0:
            return 1e9
        exploit = self.total_value / self.visit_count
        explore = c * (((total_visits + 1) ** 0.5) / (self.visit_count ** 0.5))
        return exploit + explore + novelty_bonus


class IdeaTree(BaseModel):
    tree_id: str = Field(default_factory=lambda: f"tree-{uuid.uuid4().hex[:8]}")
    research_query: str
    nodes: dict[str, IdeaTreeNode] = Field(default_factory=dict)
    root_ids: list[str] = Field(default_factory=list)
    total_visits: int = 0
    best_node_id: str | None = None


class JudgeScore(BaseModel):
    judge_id: Literal["conservative", "generalist", "practitioner"]
    novelty: float = Field(ge=0.0, le=1.0)
    feasibility: float = Field(ge=0.0, le=1.0)
    mechanism_coherence: float = Field(ge=0.0, le=1.0)
    executability: float = Field(ge=0.0, le=1.0)
    strategic_importance: float = Field(ge=0.0, le=1.0)
    reasoning: dict[str, str] = Field(default_factory=dict)


class PanelVerdict(BaseModel):
    hypo_id: str
    scores: list[JudgeScore]
    novelty_mean: float
    novelty_var: float
    feasibility_mean: float
    feasibility_var: float
    coherence_mean: float
    coherence_var: float
    executability_mean: float
    executability_var: float
    importance_mean: float
    importance_var: float
    controversy_score: float
    panel_composite: float


class MemoryEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:10]}")
    session_id: str
    hypothesis_title: str
    hypothesis_embedding: list[float] = Field(default_factory=list)
    strategy: str
    composite_score: float = 0.0
    panel_composite: float | None = None
    metric_delta: float | None = None
    failure_reason: str | None = None
    domain_tags: list[str] = Field(default_factory=list)


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


class GeneratorOutputV2(BaseModel):
    hypotheses: list[HypothesisV2] = Field(default_factory=list)
    panel_verdicts: list[PanelVerdict] = Field(default_factory=list)
    portfolio: list[PanelVerdict] = Field(default_factory=list)
    memory_context: str = ""
    reasoning_context: str = ""
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
    session_id: str | None = None
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
    hypothesis_pool_v2: list[HypothesisV2] = Field(default_factory=list)
    idea_tree: IdeaTree | None = None
    memory_context: str = ""
    memory_entries: list[MemoryEntry] = Field(default_factory=list)
    tribunal_verdicts: dict[str, TribunalVerdict] = Field(default_factory=dict)
    tribunal_verdicts_v2: dict[str, dict] = Field(default_factory=dict)
    refined_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)
    refined_hypotheses_v2: list[HypothesisV2] = Field(default_factory=list)
    dimension_scores: dict[str, DimensionScores] = Field(default_factory=dict)
    panel_verdicts: dict[str, PanelVerdict] = Field(default_factory=dict)
    ranked_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)
    final_portfolio: ResearchPortfolio | None = None
    final_portfolio_v2: list[PanelVerdict] = Field(default_factory=list)
    refinement_cycle: int = 0
    errors: list[str] = Field(default_factory=list)
