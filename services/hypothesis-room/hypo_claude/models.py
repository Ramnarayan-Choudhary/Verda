"""
Pydantic models for the 7-layer Epistemic Engine hypothesis pipeline.

Layer 0: Multi-Document Intelligence (PaperIntelligence, ResearchLandscape)
Layer 1: Research Space Cartography (GapAnalysis, ResearchSpaceMap, ContestableAssumption, SOTACeiling)
Layer 2: Multi-Strategy Generation (StructuredHypothesis, CausalChain, ExperimentSketch, IdeaTree)
Layer 3: Adversarial Tribunal (TribunalVerdict, 5 critique models + MechanismValidator)
Layer 4: Panel Evaluation (DimensionScores, JudgeScore, controversy_score)
Layer 5: Portfolio Construction (ResearchPortfolio, 5-slot risk tiers)
Layer 6: Cross-Session Memory (MemoryEntry)
"""

from __future__ import annotations

import math
import uuid
from enum import Enum
from typing import Any, Literal

import numpy as np
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


class EvidenceStatement(BaseModel):
    """A single claim with cross-paper support/contradiction tracking."""
    claim: str = ""
    supporting_papers: list[str] = Field(default_factory=list)
    contradicting_papers: list[str] = Field(default_factory=list)
    confidence: Literal["strong", "moderate", "weak", "contested"] = "moderate"
    supporting_quotes: list[str] = Field(default_factory=list)


class EvidenceConsensus(BaseModel):
    """Cross-paper agreement/disagreement analysis (Consensus AI-inspired)."""
    statements: list[EvidenceStatement] = Field(default_factory=list)
    overall_agreement_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    key_disagreements: list[str] = Field(default_factory=list)


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

    # Evidence consensus (Consensus AI-inspired — shows agreement across papers)
    evidence_consensus: EvidenceConsensus | None = None

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


class ContestableAssumption(BaseModel):
    """A shared assumption that can be inverted to generate hypotheses."""
    assumption: str = ""
    held_because: str = ""
    vulnerable_because: str = ""
    inversion_prediction: str = ""
    supporting_paper_ids: list[str] = Field(default_factory=list)


class SOTACeiling(BaseModel):
    """Current state-of-the-art ceiling and what would break it."""
    best_method: str = ""
    ceiling_metric: str = ""
    ceiling_value: str = ""
    structural_reason: str = ""
    what_would_break_it: str = ""


class ResearchSpaceMap(BaseModel):
    """Cartography output — the 4-type gap taxonomy with deep structural analysis."""
    knowledge_gaps: list[GapAnalysis] = Field(default_factory=list)
    method_gaps: list[GapAnalysis] = Field(default_factory=list)
    assumption_gaps: list[GapAnalysis] = Field(default_factory=list)
    theoretical_gaps: list[GapAnalysis] = Field(default_factory=list)
    high_value_targets: list[str] = Field(
        default_factory=list,
        description="Top 5-7 gap_ids by combined value",
    )

    # Deep structural analysis (Layer 1 enrichment)
    contestable_assumptions: list[ContestableAssumption] = Field(default_factory=list)
    sota_ceiling: SOTACeiling | None = None
    failed_approaches: list[str] = Field(default_factory=list)

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


class MutationOp(str, Enum):
    """Directed mutation operators for hypothesis evolution."""
    DEEPEN_MECHANISM = "deepen_mechanism"
    NARROW_SCOPE = "narrow_scope"
    BROADEN_CLAIM = "broaden_claim"
    INJECT_ANALOGY = "inject_analogy"
    CHALLENGE_ASSUME = "challenge_assume"
    RECOMBINE = "recombine"
    SHARPEN_FALSIFY = "sharpen_falsify"


class CausalChain(BaseModel):
    """Formal causal chain: intervention -> intermediate steps -> outcome."""
    intervention: str = ""
    intermediate: str = ""
    outcome: str = ""
    conditions: str = ""
    breaks_when: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_to_str(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict):
            return str(v)
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v)

    model_config = {"extra": "ignore"}


class ExperimentSketch(BaseModel):
    """Concrete experiment design for hypothesis testing."""
    design: str = ""
    baseline: str = ""
    primary_metric: str = ""
    success_threshold: str = ""
    compute_estimate: str = ""
    time_horizon: str = ""
    required_data: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_to_str(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict):
            return str(v)
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v)

    model_config = {"extra": "ignore"}


class MinimalTest(BaseModel):
    """Minimum viable experiment specification."""
    dataset: str = ""
    baseline: str = ""
    primary_metric: str = ""
    success_threshold: str = ""
    estimated_compute: str = ""
    estimated_timeline: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_to_str(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict):
            return str(v)
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v)

    model_config = {"extra": "ignore"}


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

    # Formal causal chain (architecture doc Layer 2)
    causal_chain: CausalChain | None = None
    experiment_sketch: ExperimentSketch | None = None

    # Testability
    falsification_criterion: str = ""
    minimal_test: MinimalTest = Field(default_factory=MinimalTest)

    # Novelty
    closest_existing_work: str = ""
    novelty_claim: str = ""
    grounding_paper_ids: list[str] = Field(default_factory=list)

    # Confidence calibration
    expected_outcome_if_true: str = ""
    expected_outcome_if_false: str = ""
    theoretical_basis: str = ""

    model_config = {"extra": "ignore"}

    @field_validator("grounding_paper_ids", mode="before")
    @classmethod
    def _coerce_paper_ids(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []


# ── IdeaTree — Lineage tracking + UCB1 selection ────────────────────

class TreeNode(BaseModel):
    """A node in the IdeaTree — tracks hypothesis lineage and MCGS signals."""
    node_id: str = Field(default_factory=lambda: _gen_id("tn"))
    hypothesis_id: str = ""
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    mutation_op: str | None = None
    visit_count: int = 0
    total_value: float = 0.0
    is_pruned: bool = False
    generation_strategy: str = ""

    def ucb1_score(self, total_visits: int, c: float = 1.41) -> float:
        """Upper Confidence Bound for exploration-exploitation balance."""
        if self.visit_count == 0:
            return float("inf")
        exploitation = self.total_value / self.visit_count
        exploration = c * math.sqrt(math.log(total_visits) / self.visit_count)
        return exploitation + exploration


class IdeaTree(BaseModel):
    """Tree structure for tracking hypothesis lineage with MCGS signals."""
    tree_id: str = Field(default_factory=lambda: _gen_id("tree"))
    nodes: dict[str, TreeNode] = Field(default_factory=dict)
    root_ids: list[str] = Field(default_factory=list)
    total_visits: int = 0
    best_node_id: str | None = None

    model_config = {"arbitrary_types_allowed": True}

    def add_node(
        self,
        hypothesis: StructuredHypothesis,
        parent_id: str | None = None,
        mutation_op: str | None = None,
    ) -> TreeNode:
        """Add a hypothesis as a node in the tree."""
        node = TreeNode(
            hypothesis_id=hypothesis.id,
            parent_ids=[parent_id] if parent_id else [],
            mutation_op=mutation_op,
            generation_strategy=hypothesis.generation_strategy,
        )
        self.nodes[node.node_id] = node
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].child_ids.append(node.node_id)
        if not parent_id:
            self.root_ids.append(node.node_id)
        return node

    def get_frontier(self) -> list[TreeNode]:
        """Get leaf nodes that haven't been pruned."""
        return [
            n for n in self.nodes.values()
            if not n.is_pruned and not n.child_ids
        ]

    def select_by_ucb1(self, k: int = 5) -> list[TreeNode]:
        """Select top-K frontier nodes by UCB1 score."""
        frontier = self.get_frontier()
        if not frontier:
            return []
        self.total_visits = max(1, self.total_visits)
        scored = sorted(
            frontier,
            key=lambda n: n.ucb1_score(self.total_visits),
            reverse=True,
        )
        return scored[:k]

    def backpropagate(self, node_id: str, value: float, decay: float = 0.7) -> None:
        """Propagate value signal up the tree with decay."""
        node = self.nodes.get(node_id)
        if not node:
            return
        node.visit_count += 1
        node.total_value += value
        self.total_visits += 1
        current_value = value
        for pid in node.parent_ids:
            current_value *= decay
            parent = self.nodes.get(pid)
            if parent:
                parent.visit_count += 1
                parent.total_value += current_value

    def get_strategy_distribution(self) -> dict[str, int]:
        """Count hypotheses per generation strategy in frontier."""
        dist: dict[str, int] = {}
        for node in self.get_frontier():
            s = node.generation_strategy or "unknown"
            dist[s] = dist.get(s, 0) + 1
        return dist


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


class ExecutabilityCritique(BaseModel):
    """Can this be implemented end-to-end with available tools?"""
    implementation_feasible: bool = True
    required_libraries: list[str] = Field(default_factory=list)
    novel_infra_needed: bool = False
    implementation_risk: Literal["low", "medium", "high"] = "medium"
    exec_score: float = Field(default=0.5, ge=0.0, le=1.0)
    blocking_issues: list[str] = Field(default_factory=list)


class MechanismValidation(BaseModel):
    """Logical consistency check on the causal chain."""
    causal_chain_complete: bool = True
    identified_gaps: list[str] = Field(default_factory=list)
    strengthened_mechanism: str = ""
    logical_score: float = Field(default=0.5, ge=0.0, le=1.0)
    is_logically_valid: bool = True
    contradictions: list[str] = Field(default_factory=list)


class TribunalVerdict(BaseModel):
    """Aggregated verdict from all 5 critics + mechanism validator."""
    hypothesis_id: str = ""

    domain_validity: DomainCritique = Field(default_factory=DomainCritique)
    methodology: MethodologyCritique = Field(default_factory=MethodologyCritique)
    devils_advocate: DevilsAdvocateCritique = Field(default_factory=DevilsAdvocateCritique)
    resource_reality: ResourceCritique = Field(default_factory=ResourceCritique)
    executability: ExecutabilityCritique = Field(default_factory=ExecutabilityCritique)
    mechanism_validation: MechanismValidation = Field(default_factory=MechanismValidation)

    # Synthesis
    overall_verdict: Literal["advance", "revise", "abandon"] = "revise"
    primary_weakness: str = ""
    revision_directive: str = ""
    mutation_cycle: int = 0


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
    "mechanistic_quality": 0.20,
    "novelty": 0.15,
    "testability": 0.20,
    "impact": 0.10,
    "feasibility": 0.20,
    "specificity": 0.10,
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


def compute_panel_composite(
    judge_scores: list[JudgeScore],
    risk_appetite: Literal["conservative", "balanced", "moonshot"] = "balanced",
) -> float:
    """Confidence-weighted composite across panel judges with risk-appetite modes.

    Each judge's contribution is: persona_weight * confidence * composite_score.
    This means a high-confidence judge has more influence than a low-confidence one.
    """
    if not judge_scores:
        return 0.0

    appetite_weights = {
        "conservative": {"conservative": 0.50, "generalist": 0.25, "practitioner": 0.25},
        "balanced": JUDGE_WEIGHTS,
        "moonshot": {"conservative": 0.15, "generalist": 0.50, "practitioner": 0.35},
    }
    weights = appetite_weights.get(risk_appetite, JUDGE_WEIGHTS)

    total = 0.0
    weight_sum = 0.0
    for js in judge_scores:
        persona_w = weights.get(js.judge_persona, 0.33)
        # Scale by confidence: confident judges count more
        effective_w = persona_w * (0.5 + 0.5 * js.confidence)  # range: 0.5x to 1.0x
        total += js.scores.composite * effective_w
        weight_sum += effective_w
    return round(total / weight_sum, 1) if weight_sum > 0 else 0.0


def compute_confidence(judge_scores: list[JudgeScore]) -> float:
    """Compute an overall confidence score (0-1) from the judge panel.

    Confidence is high when:
    - Judges agree with each other (low controversy)
    - Judges are individually confident
    - The composite scores are consistent
    """
    if not judge_scores:
        return 0.0

    # Factor 1: Mean judge self-confidence (0-1)
    mean_confidence = sum(js.confidence for js in judge_scores) / len(judge_scores)

    # Factor 2: Agreement between judges (inverse of controversy, normalized to 0-1)
    if len(judge_scores) >= 2:
        composites = [js.scores.composite for js in judge_scores]
        mean_comp = sum(composites) / len(composites)
        if mean_comp > 0:
            # Coefficient of variation: lower = more agreement
            std = (sum((c - mean_comp) ** 2 for c in composites) / len(composites)) ** 0.5
            cv = std / mean_comp
            agreement = max(0.0, 1.0 - cv)  # cv of 0 = perfect agreement = 1.0
        else:
            agreement = 0.0
    else:
        agreement = mean_confidence  # Single judge: trust their confidence

    # Combined: 60% agreement, 40% self-confidence
    return round(0.6 * agreement + 0.4 * mean_confidence, 3)


def compute_controversy_score(judge_scores: list[JudgeScore]) -> float:
    """Mean variance across dimensions — high = judges disagree = interesting."""
    if len(judge_scores) < 2:
        return 0.0
    variances = []
    for dim in DIMENSION_WEIGHTS:
        values = [getattr(js.scores, dim, 0) for js in judge_scores]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        variances.append(variance)
    return round(sum(variances) / len(variances), 2) if variances else 0.0


# ═══════════════════════════════════════════════════════════════════════
# LAYER 5 — Strategic Portfolio Construction (5 risk-tiered slots)
# ═══════════════════════════════════════════════════════════════════════

class PortfolioSlot(BaseModel):
    """Definition of a risk-tiered portfolio slot."""
    name: str
    risk_tier: Literal["safe", "balanced", "moonshot"]
    time_horizon: str
    min_novelty: float = 0.0
    min_feasibility: float = 0.0


# 5 standard portfolio slots (from architecture doc Layer 5)
PORTFOLIO_SLOTS = [
    PortfolioSlot(name="A", risk_tier="safe", time_horizon="1 month", min_novelty=0.30, min_feasibility=0.80),
    PortfolioSlot(name="B", risk_tier="safe", time_horizon="3 months", min_novelty=0.40, min_feasibility=0.65),
    PortfolioSlot(name="C", risk_tier="balanced", time_horizon="3 months", min_novelty=0.65, min_feasibility=0.55),
    PortfolioSlot(name="D", risk_tier="moonshot", time_horizon="6 months", min_novelty=0.80, min_feasibility=0.30),
    PortfolioSlot(name="E", risk_tier="moonshot", time_horizon="12+ months", min_novelty=0.75, min_feasibility=0.25),
]


class PortfolioHypothesis(BaseModel):
    """A hypothesis with its slot assignment and full evaluation context."""
    hypothesis: StructuredHypothesis = Field(default_factory=StructuredHypothesis)
    portfolio_slot: Literal["safe", "medium", "moonshot"] = "medium"
    slot_name: str = ""
    dimension_scores: DimensionScores = Field(default_factory=DimensionScores)
    tribunal_verdict: TribunalVerdict = Field(default_factory=TribunalVerdict)
    panel_composite: float = 0.0
    controversy_score: float = 0.0
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
    """The final output — 3-5 strategically selected hypotheses in risk-tiered slots."""
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
    def balanced_hypotheses(self) -> list[PortfolioHypothesis]:
        return [h for h in self.hypotheses if h.portfolio_slot in ("medium", "balanced")]

    @property
    def moonshot_hypotheses(self) -> list[PortfolioHypothesis]:
        return [h for h in self.hypotheses if h.portfolio_slot == "moonshot"]


# ═══════════════════════════════════════════════════════════════════════
# LAYER 6 — Cross-Session Memory
# ═══════════════════════════════════════════════════════════════════════

class MemoryEntry(BaseModel):
    """A hypothesis outcome stored for cross-session memory."""
    entry_id: str = Field(default_factory=lambda: _gen_id("mem"))
    session_id: str = ""
    hypothesis_title: str = ""
    strategy: str = ""
    composite_score: float = 0.0
    panel_composite: float = 0.0
    metric_delta: float | None = None
    failure_reason: str | None = None
    domain_tags: list[str] = Field(default_factory=list)
    created_at: str = ""

    @property
    def is_negative(self) -> bool:
        return (self.metric_delta is not None and self.metric_delta < 0) or self.panel_composite < 0.4

    @property
    def is_positive(self) -> bool:
        return (self.metric_delta is not None and self.metric_delta > 0.05) or self.panel_composite > 0.7


class MemoryContext(BaseModel):
    """Memory conditioning context injected at pipeline start."""
    negative_entries: list[MemoryEntry] = Field(default_factory=list)
    positive_entries: list[MemoryEntry] = Field(default_factory=list)
    blocking_text: str = ""
    building_text: str = ""


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
    max_hypotheses_per_strategy: int = Field(default=1, ge=1, le=10)
    tribunal_cycles: int = Field(default=1, ge=1, le=5)
    portfolio_safe_slots: int = Field(default=2, ge=1, le=3)
    portfolio_medium_slots: int = Field(default=2, ge=1, le=3)
    portfolio_moonshot_slots: int = Field(default=1, ge=0, le=2)
    dedup_threshold: float = Field(default=0.80, ge=0.5, le=1.0)
    domain: str = "other"
    stage_timeouts: dict[str, int] = Field(default_factory=dict)

    # Deep Research Mode (SciSpace-inspired iterative search-read-refine)
    enable_deep_research: bool = Field(default=False, description="Enable iterative literature search before hypothesis generation")
    deep_research_rounds: int = Field(default=3, ge=1, le=5)
    max_papers_per_round: int = Field(default=10, ge=3, le=25)
    follow_citations: bool = Field(default=True, description="Follow citation networks during deep research")

    # Human-in-the-loop checkpoints
    enable_checkpoints: bool = Field(default=False, description="Pause pipeline at key stages for user steering")
    checkpoint_stages: list[str] = Field(default_factory=lambda: ["layer0", "layer1", "layer2"])

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
    idea_tree: IdeaTree | None = None

    # Layer 3: Tribunal
    tribunal_verdicts: dict[str, TribunalVerdict] = Field(default_factory=dict)
    refined_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)
    refinement_cycle: int = 0

    # Layer 4: Evaluation
    panel_scores: dict[str, list[JudgeScore]] = Field(default_factory=dict)
    ranked_hypotheses: list[StructuredHypothesis] = Field(default_factory=list)

    # Layer 5: Portfolio
    research_portfolio: ResearchPortfolio | None = None

    # Layer 6: Memory
    memory_context: MemoryContext | None = None

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
    type: Literal["progress", "warning", "complete", "error", "checkpoint"]
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
