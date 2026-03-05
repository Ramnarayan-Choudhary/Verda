"""
Pydantic models for the hypothesis generation pipeline.

CRITICAL: These models must serialize to JSON shapes identical to the TypeScript
types in vreda-app/src/lib/agents/strategist-room/hypothesis/types.ts so that
the existing HypothesisSelector.tsx frontend component can render them.

Reference papers cited in field descriptions:
- arXiv:2502.18864 (AI Co-Scientist — debate-evolve loop, Elo ranking)
- arXiv:2510.09901 (Knowledge-grounded generation, KG novelty checks)
- arXiv:2409.04109 (Overgeneration with diversity, tournament ranking)
- AI-Researcher (HKUDS) — atomic operator extraction, ResearchFrame
- HypoRefine (ChicagoHAI) — wrong-example-bank, iterative refinement
- open_deep_research (LangChain) — iterative gap validation
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────
# Hypothesis Types (matches TS HypothesisType)
# ──────────────────────────────────────────────

class HypothesisType(str, Enum):
    """10 hypothesis types — domain-aware selection."""
    SCALE = "scale"
    MODALITY_SHIFT = "modality_shift"
    ARCHITECTURE_ABLATION = "architecture_ablation"
    CROSS_DOMAIN_TRANSFER = "cross_domain_transfer"
    EFFICIENCY_OPTIMIZATION = "efficiency_optimization"
    FAILURE_MODE_ANALYSIS = "failure_mode_analysis"
    DATA_AUGMENTATION = "data_augmentation"
    THEORETICAL_EXTENSION = "theoretical_extension"
    COMBINATION = "combination"
    CONSTRAINT_RELAXATION = "constraint_relaxation"


DOMAIN_HYPOTHESIS_TYPES: dict[str, list[HypothesisType]] = {
    "cv": [HypothesisType.SCALE, HypothesisType.ARCHITECTURE_ABLATION, HypothesisType.MODALITY_SHIFT, HypothesisType.EFFICIENCY_OPTIMIZATION, HypothesisType.DATA_AUGMENTATION],
    "nlp": [HypothesisType.SCALE, HypothesisType.CROSS_DOMAIN_TRANSFER, HypothesisType.ARCHITECTURE_ABLATION, HypothesisType.EFFICIENCY_OPTIMIZATION, HypothesisType.COMBINATION],
    "ml": [HypothesisType.SCALE, HypothesisType.ARCHITECTURE_ABLATION, HypothesisType.THEORETICAL_EXTENSION, HypothesisType.EFFICIENCY_OPTIMIZATION, HypothesisType.FAILURE_MODE_ANALYSIS],
    "robotics": [HypothesisType.MODALITY_SHIFT, HypothesisType.CONSTRAINT_RELAXATION, HypothesisType.EFFICIENCY_OPTIMIZATION, HypothesisType.FAILURE_MODE_ANALYSIS, HypothesisType.COMBINATION],
    "biology": [HypothesisType.CROSS_DOMAIN_TRANSFER, HypothesisType.DATA_AUGMENTATION, HypothesisType.CONSTRAINT_RELAXATION, HypothesisType.SCALE, HypothesisType.THEORETICAL_EXTENSION],
    "chemistry": [HypothesisType.CROSS_DOMAIN_TRANSFER, HypothesisType.CONSTRAINT_RELAXATION, HypothesisType.DATA_AUGMENTATION, HypothesisType.COMBINATION, HypothesisType.THEORETICAL_EXTENSION],
    "physics": [HypothesisType.THEORETICAL_EXTENSION, HypothesisType.SCALE, HypothesisType.CONSTRAINT_RELAXATION, HypothesisType.FAILURE_MODE_ANALYSIS, HypothesisType.COMBINATION],
    "materials": [HypothesisType.CROSS_DOMAIN_TRANSFER, HypothesisType.COMBINATION, HypothesisType.DATA_AUGMENTATION, HypothesisType.CONSTRAINT_RELAXATION, HypothesisType.SCALE],
    "other": [HypothesisType.SCALE, HypothesisType.MODALITY_SHIFT, HypothesisType.ARCHITECTURE_ABLATION, HypothesisType.EFFICIENCY_OPTIMIZATION, HypothesisType.CROSS_DOMAIN_TRANSFER],
}


# ──────────────────────────────────────────────
# Hypothesis Archetypes (mechanistic mutations)
# ──────────────────────────────────────────────
# Inspired by AI-Researcher + NeurIPS reviewer methodology.
# Each archetype prescribes a specific experimental methodology,
# not just a category.

class HypothesisArchetype(str, Enum):
    """5 mechanistic archetypes — each is a precise experimental methodology."""
    MECHANISTIC_PROBE = "mechanistic_probe"       # Ablate the claimed mechanism
    REGIME_FLIP = "regime_flip"                   # Apply operator to opposite regime
    BASELINE_CLOSURE = "baseline_closure"         # Run missing SOTA comparison
    FAILURE_INVERSION = "failure_inversion"       # Construct exact failure boundary
    OPERATOR_INJECTION = "operator_injection"     # Inject operator from related paper


ARCHETYPE_DESCRIPTIONS: dict[HypothesisArchetype, str] = {
    HypothesisArchetype.MECHANISTIC_PROBE: (
        "Ablate the claimed mechanism. If the result disappears, the mechanism is confirmed. "
        "If it persists, the mechanism is wrong or incomplete."
    ),
    HypothesisArchetype.REGIME_FLIP: (
        "Apply the operator to the opposite regime it was designed for: "
        "low-data when it assumed high-data, small-model when it assumed large, "
        "edge-device when it assumed cloud, multilingual when it assumed English-only."
    ),
    HypothesisArchetype.BASELINE_CLOSURE: (
        "Run the missing SOTA comparison on the same benchmark. "
        "The paper omitted key baselines — run them and compare fairly."
    ),
    HypothesisArchetype.FAILURE_INVERSION: (
        "Construct the exact condition where the method breaks. "
        "Measure the collapse boundary — at what point does performance degrade catastrophically?"
    ),
    HypothesisArchetype.OPERATOR_INJECTION: (
        "Take operator O from a related paper. Inject it into the focal architecture. "
        "Predict the emergent interaction — synergy or interference?"
    ),
}

# Map gap types to best-fit archetypes
GAP_TO_ARCHETYPE: dict[str, list[HypothesisArchetype]] = {
    "empirical": [HypothesisArchetype.BASELINE_CLOSURE, HypothesisArchetype.MECHANISTIC_PROBE],
    "theoretical": [HypothesisArchetype.MECHANISTIC_PROBE, HypothesisArchetype.FAILURE_INVERSION],
    "robustness": [HypothesisArchetype.FAILURE_INVERSION, HypothesisArchetype.REGIME_FLIP],
    "scaling": [HypothesisArchetype.REGIME_FLIP, HypothesisArchetype.BASELINE_CLOSURE],
    "application": [HypothesisArchetype.OPERATOR_INJECTION, HypothesisArchetype.REGIME_FLIP],
}

# Map archetypes to legacy HypothesisType for frontend compatibility
ARCHETYPE_TO_TYPE: dict[HypothesisArchetype, HypothesisType] = {
    HypothesisArchetype.MECHANISTIC_PROBE: HypothesisType.ARCHITECTURE_ABLATION,
    HypothesisArchetype.REGIME_FLIP: HypothesisType.CONSTRAINT_RELAXATION,
    HypothesisArchetype.BASELINE_CLOSURE: HypothesisType.SCALE,
    HypothesisArchetype.FAILURE_INVERSION: HypothesisType.FAILURE_MODE_ANALYSIS,
    HypothesisArchetype.OPERATOR_INJECTION: HypothesisType.COMBINATION,
}


# ──────────────────────────────────────────────
# ResearchFrame (AI-Researcher: atomic operator extraction)
# ──────────────────────────────────────────────

class ClaimedGain(BaseModel):
    """A specific quantitative claim from the paper."""
    operator: str               # Named technique: "LoRA", "STE", "sparse attention"
    gain: str                   # "+Y% on Z"
    condition: str = ""         # "under W" — e.g., "on English-only tasks"


class ResearchFrame(BaseModel):
    """Deep mechanistic decomposition — operators only, no summaries.

    Inspired by AI-Researcher (HKUDS): atomic concept decomposition
    with math↔code bidirectional mapping.
    """
    task_family: Literal["vision", "nlp", "rl", "theory", "systems", "bio", "other"] = "other"
    core_operators: list[str] = Field(
        default_factory=list,
        description="Exact named techniques: 'STE', 'LoRA', 'sparse attention', 'contrastive loss'"
    )
    core_mechanism: str = Field(
        default="",
        description="One sentence: the specific intervention that drives results"
    )
    claimed_gains: list[ClaimedGain] = Field(default_factory=list)
    assumptions: list[str] = Field(
        default_factory=list,
        description="'IID data', 'English-only', '>40GB VRAM', 'pre-trained backbone'"
    )
    explicit_limits: list[str] = Field(
        default_factory=list,
        description="What the authors explicitly admit they did not test"
    )
    implicit_limits: list[str] = Field(
        default_factory=list,
        description="What a domain expert sees missing but the paper ignores"
    )
    missing_baselines: list[str] = Field(
        default_factory=list,
        description="SOTA methods omitted from comparison"
    )
    untested_axes: list[str] = Field(
        default_factory=list,
        description="'scale', 'OOD', 'low-data', 'adversarial', 'quantization', 'multilingual'"
    )

    @field_validator("task_family", mode="before")
    @classmethod
    def _normalize_task_family(cls, value: Any) -> str:
        """Coerce fuzzy LLM labels into the strict task family enum."""
        if not isinstance(value, str):
            return "other"
        text = value.strip().lower()
        if not text:
            return "other"

        allowed = {"vision", "nlp", "rl", "theory", "systems", "bio", "other"}
        if text in allowed:
            return text

        aliases: dict[str, tuple[str, ...]] = {
            "vision": ("vision", "cv", "image", "video"),
            "nlp": ("nlp", "language", "llm", "text", "dialog"),
            "rl": ("rl", "reinforcement", "policy", "agent training"),
            "theory": ("theory", "theoretical", "proof", "bound"),
            "systems": ("systems", "distributed", "inference", "serving", "compiler", "database"),
            "bio": ("bio", "biology", "biomedical", "genomics", "proteomics", "drug discovery"),
        }
        for normalized, markers in aliases.items():
            if any(marker in text for marker in markers):
                return normalized
        return "other"


# ──────────────────────────────────────────────
# MetaGap (iteratively-validated research gaps)
# ──────────────────────────────────────────────
# Inspired by open_deep_research: 3-round identify→check→refine loop.

class MetaGap(BaseModel):
    """A research gap that survived 3 rounds of iterative validation."""
    gap_id: str = Field(default_factory=lambda: f"G{uuid.uuid4().hex[:4].upper()}")
    gap_type: Literal["empirical", "theoretical", "robustness", "scaling", "application"]
    statement: str = Field(
        description="'No work tests [operator X] under [constraint Y] on [dataset class Z]'"
    )
    why_it_matters: str = Field(
        description="Changes understanding of [mechanism] because [reason]"
    )
    nearest_prior_work: str = Field(
        default="",
        description="Closest paper that tried but did not close this gap"
    )
    already_solved: bool = False
    iteration_history: list[str] = Field(
        default_factory=list,
        description="Track how this gap was refined across iterations"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_keys(cls, value: Any) -> Any:
        """Accept common LLM key variants to reduce validation retries."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "gap_id" not in data and "id" in data:
            data["gap_id"] = data.get("id")
        if "gap_type" not in data:
            data["gap_type"] = data.get("type") or data.get("category") or data.get("gapType")
        if "statement" not in data:
            data["statement"] = (
                data.get("description")
                or data.get("gap_statement")
                or data.get("gap")
                or ""
            )
        if "why_it_matters" not in data:
            data["why_it_matters"] = (
                data.get("why")
                or data.get("importance")
                or data.get("rationale")
                or ""
            )
        if "nearest_prior_work" not in data:
            data["nearest_prior_work"] = (
                data.get("closest_paper")
                or data.get("prior_work")
                or data.get("nearest_work")
                or ""
            )
        if "already_solved" not in data and "solved" in data:
            data["already_solved"] = bool(data.get("solved"))
        return data

    @field_validator("iteration_history", mode="before")
    @classmethod
    def _coerce_iteration_history(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []


class MetaGapAnalysis(BaseModel):
    """Result of iterative gap synthesis — replaces single-shot GapAnalysis for seeding."""
    gaps: list[MetaGap] = Field(default_factory=list)
    landscape_summary: str = ""
    dominant_trends: list[str] = Field(default_factory=list)
    underexplored_areas: list[str] = Field(default_factory=list)
    iterations_completed: int = 0


# ──────────────────────────────────────────────
# Scoring (matches TS DimensionScores)
# ──────────────────────────────────────────────

class DimensionScores(BaseModel):
    """6-dimensional scoring — each 0-100. Matches TS DimensionScores."""
    novelty: int = Field(default=0, ge=0, le=100, description="How new compared to existing work")
    feasibility: int = Field(default=0, ge=0, le=100, description="Can be done with available resources")
    impact: int = Field(default=0, ge=0, le=100, description="How significant would results be")
    grounding: int = Field(default=0, ge=0, le=100, description="How well-supported by evidence")
    testability: int = Field(default=0, ge=0, le=100, description="How clear/falsifiable is the prediction")
    clarity: int = Field(default=0, ge=0, le=100, description="How well-articulated is the hypothesis")


DIMENSION_WEIGHTS: dict[str, float] = {
    "novelty": 0.25,
    "feasibility": 0.20,
    "impact": 0.20,
    "grounding": 0.15,
    "testability": 0.10,
    "clarity": 0.10,
}


def compute_composite_score(scores: DimensionScores) -> int:
    """Weighted composite score — matches TS computeCompositeScore()."""
    total = sum(
        getattr(scores, dim) * weight
        for dim, weight in DIMENSION_WEIGHTS.items()
    )
    return round(total)


# ──────────────────────────────────────────────
# Research Gap (matches TS ResearchGap / GapAnalysis)
# ──────────────────────────────────────────────

class ResearchGap(BaseModel):
    id: str = Field(default_factory=lambda: f"gap-{uuid.uuid4().hex[:8]}")
    gap_type: Literal[
        "unexplored_direction",
        "contradictory_findings",
        "missing_evaluation",
        "scalability_question",
        "cross_domain_opportunity",
    ]
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    related_paper_titles: list[str] = Field(default_factory=list)
    potential_impact: Literal["incremental", "moderate", "significant", "transformative"]
    confidence: int = Field(default=50, ge=0, le=100)


class GapAnalysis(BaseModel):
    """Research landscape gap analysis — matches TS GapAnalysis."""
    gaps: list[ResearchGap] = Field(default_factory=list)
    landscape_summary: str = ""
    dominant_trends: list[str] = Field(default_factory=list)
    underexplored_areas: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Evidence & Novelty (matches TS EvidenceBasis / NoveltyAssessment)
# ──────────────────────────────────────────────

class SupportingPaper(BaseModel):
    title: str
    arxiv_id: str | None = None
    year: int | None = None
    citation_count: int = 0
    relevance: str = ""


class EvidenceBasis(BaseModel):
    supporting_papers: list[SupportingPaper] = Field(default_factory=list)
    prior_results: str = ""
    key_insight: str = ""
    gap_exploited: str = ""


class NoveltyAssessment(BaseModel):
    is_novel: bool = True
    similar_work: list[str] = Field(default_factory=list)
    what_is_new: str = ""
    novelty_score: int = Field(default=50, ge=0, le=100)
    novelty_type: Literal[
        "entirely_new", "new_combination", "new_application", "incremental_extension"
    ] = "new_combination"


# ──────────────────────────────────────────────
# Experiment Design — Enhanced with MVE + Falsification
# ──────────────────────────────────────────────

class ExperimentSpec(BaseModel):
    """Precise experiment specification — archetype-aware."""
    intervention: str = ""          # The single precise change
    control: str = ""               # What stays fixed
    dataset: str = ""               # Named real dataset only
    metric: str = ""                # Named metric only
    prediction: str = ""            # Number or direction with magnitude
    falsification_threshold: str = ""  # "Dead if: [specific condition]"


class ResourceSpec(BaseModel):
    """Compute resource requirements for MVE."""
    model: str = ""                 # Exact model name
    gpu_hours: int = Field(default=24, ge=0, description="MVE-realistic GPU hours")


class AdversarialDefense(BaseModel):
    """Strongest reviewer objection + defense."""
    kill_switch: str = ""           # Strongest reviewer objection
    defense: str = ""               # Design change that neutralizes it


class NoveltySpec(BaseModel):
    """Structured novelty assessment per hypothesis."""
    closest_paper: str = ""         # Most similar existing work
    why_distinct: str = ""          # One sentence
    verdict: Literal["substantial", "incremental"] = "incremental"


class ExperimentDesign(BaseModel):
    """Experiment design — matches TS ExperimentDesign + enhanced fields."""
    baseline: str = ""
    independent_variables: list[str] = Field(default_factory=list)
    dependent_variables: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    dataset_requirements: str = ""
    estimated_duration: str = ""
    code_changes: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Critic Assessment (matches TS CriticAssessment)
# ──────────────────────────────────────────────

class CriticAssessment(BaseModel):
    hypothesis_id: str
    feasibility_issues: list[str] = Field(default_factory=list)
    grounding_score: float = Field(default=0.5, ge=0.0, le=1.0)
    overlap_with_literature: str = ""
    suggested_improvements: list[str] = Field(default_factory=list)
    verdict: Literal["strong", "viable", "weak"] = "viable"
    revised_scores: DimensionScores | None = None
    # Enhanced critic fields
    mve_executable: bool = True
    falsification_valid: bool = True
    adversarial_defense_adequate: bool = True
    portfolio_tag: Literal["empirical", "robustness", "scaling", "theoretical"] = "empirical"


# ──────────────────────────────────────────────
# Enhanced Hypothesis (matches TS EnhancedHypothesis + archetype fields)
# ──────────────────────────────────────────────

class EnhancedHypothesis(BaseModel):
    """Full hypothesis with all metadata — matches TS EnhancedHypothesis exactly."""
    id: str = Field(default_factory=lambda: f"hyp-{uuid.uuid4().hex[:8]}")
    type: HypothesisType = HypothesisType.SCALE
    title: str = ""
    description: str = ""

    # Core scientific content
    short_hypothesis: str = ""
    testable_prediction: str = ""
    expected_outcome: str = ""

    # Archetype-driven fields (new)
    archetype: HypothesisArchetype = HypothesisArchetype.MECHANISTIC_PROBE
    statement: str = Field(
        default="",
        description="IF [exact intervention] THEN [quantified delta] on [named dataset] BECAUSE [mechanism]"
    )
    mve: list[str] = Field(
        default_factory=list,
        description="Minimum Viable Experiment — exactly 5 steps"
    )
    falsification_threshold: str = Field(
        default="",
        description="Dead if: [specific condition]"
    )
    experiment_spec: ExperimentSpec = Field(default_factory=ExperimentSpec)
    resources: ResourceSpec = Field(default_factory=ResourceSpec)
    adversarial: AdversarialDefense = Field(default_factory=AdversarialDefense)
    novelty_spec: NoveltySpec = Field(default_factory=NoveltySpec)
    portfolio_tag: Literal["empirical", "robustness", "scaling", "theoretical"] = "empirical"

    # Scoring
    scores: DimensionScores = Field(default_factory=DimensionScores)
    composite_score: int = 0

    # Implementation
    required_modifications: list[str] = Field(default_factory=list)
    estimated_complexity: Literal["low", "medium", "high"] = "medium"

    # Evidence grounding — arXiv:2510.09901
    evidence_basis: EvidenceBasis = Field(default_factory=EvidenceBasis)

    # Novelty
    novelty_assessment: NoveltyAssessment = Field(default_factory=NoveltyAssessment)

    # Experiment
    experiment_design: ExperimentDesign = Field(default_factory=ExperimentDesign)

    # Risk
    risk_factors: list[str] = Field(default_factory=list)

    # Related work
    related_work_summary: str = ""

    # Gap linkage
    addresses_gap_id: str | None = None

    # Critic (attached after review)
    critic_assessment: CriticAssessment | None = None

    # Reflection metadata — arXiv:2502.18864
    reflection_rounds_completed: int = 0

    # Elo rating — arXiv:2409.04109 tournament ranking
    elo_rating: float = Field(default=1500.0, description="Elo rating from pairwise debates")


# ──────────────────────────────────────────────
# Portfolio Audit
# ──────────────────────────────────────────────

class PortfolioAudit(BaseModel):
    """Portfolio-level quality assurance across the hypothesis set."""
    coverage: dict[str, str] = Field(
        default_factory=dict,
        description="{'empirical': 'H1', 'robustness': 'H3', ...}"
    )
    redundancies: list[str] = Field(
        default_factory=list,
        description="Any two hypotheses testing the same variable"
    )
    execution_order: list[str] = Field(
        default_factory=list,
        description="'H2 first — cheapest + highest signal', ..."
    )


# ──────────────────────────────────────────────
# SOTA Payload (strict JSON contract for VREDA Opus)
# ──────────────────────────────────────────────

class SOTAHypothesisPayload(BaseModel):
    """Strict hypothesis schema for final SOTA JSON payload."""
    id: str
    title: str = ""
    gap_id: str
    archetype: HypothesisArchetype
    statement: str
    experiment: ExperimentSpec = Field(default_factory=ExperimentSpec)
    mve: list[str] = Field(default_factory=list)
    resources: ResourceSpec = Field(default_factory=ResourceSpec)
    novelty: NoveltySpec = Field(default_factory=NoveltySpec)
    adversarial: AdversarialDefense = Field(default_factory=AdversarialDefense)


class SOTAPipelinePayload(BaseModel):
    """Top-level strict JSON payload requested for Stage-1 VREDA Opus mode."""
    research_frame: ResearchFrame | None = None
    meta_gaps: list[MetaGap] = Field(default_factory=list)
    hypotheses: list[SOTAHypothesisPayload] = Field(default_factory=list)
    portfolio_audit: PortfolioAudit = Field(default_factory=PortfolioAudit)


# ──────────────────────────────────────────────
# Pipeline Outputs (matches TS GeneratorOutput, CriticOutput, RankedHypotheses)
# ──────────────────────────────────────────────

class GeneratorOutput(BaseModel):
    """Matches TS GeneratorOutput — the shape HypothesisSelector.tsx expects."""
    hypotheses: list[EnhancedHypothesis] = Field(default_factory=list)
    reasoning_context: str = ""
    gap_analysis_used: bool = False
    reflection_rounds: int = 0
    generation_strategy: Literal["knowledge_grounded", "prompt_based"] = "knowledge_grounded"
    portfolio_audit: PortfolioAudit | None = None
    # Optional strict payload that follows the VREDA Opus JSON schema.
    sota_payload: SOTAPipelinePayload | None = None


class CriticOutput(BaseModel):
    """Matches TS CriticOutput."""
    assessments: list[CriticAssessment] = Field(default_factory=list)
    overall_recommendation: str = ""
    revision_needed: bool = False


class RankedHypotheses(BaseModel):
    """Matches TS RankedHypotheses."""
    ranked: list[EnhancedHypothesis] = Field(default_factory=list)
    ranking_rationale: str = ""
    top_recommendation: str = ""


# ──────────────────────────────────────────────
# Pipeline-Internal Models (not in TS — Python only)
# ──────────────────────────────────────────────

class HypothesisSeed(BaseModel):
    """Short 1-2 sentence seed generated in Stage 3 (overgeneration)."""
    id: str = Field(default_factory=lambda: f"seed-{uuid.uuid4().hex[:8]}")
    text: str
    type: HypothesisType = HypothesisType.SCALE
    source_prompt: str = ""  # Which prompt batch generated this
    archetype: HypothesisArchetype = HypothesisArchetype.MECHANISTIC_PROBE
    gap_id: str = ""         # Which MetaGap this seed targets


class ScoredSeed(BaseModel):
    """Seed after Stage 4 filtering — has preliminary scores."""
    seed: HypothesisSeed
    novelty_score: float = 0.0         # 0-1 from vector similarity check
    budget_estimate_usd: float = 0.0   # Rough GPU cost
    verifiability_score: float = 0.0   # 0-1 from LLM quick check
    concreteness_score: float = 0.0    # 0-1 from MVE feasibility check
    combined_score: float = 0.0        # Weighted combination for ranking
    discard_reason: str | None = None  # If filtered out, why


class FailedSeed(BaseModel):
    """HypoRefine wrong-example-bank: seeds that failed critic review."""
    seed_text: str
    failure_reason: str     # From critic: why it was "weak"
    gap_id: str = ""
    archetype: HypothesisArchetype = HypothesisArchetype.MECHANISTIC_PROBE


class PaperSummary(BaseModel):
    """Structured extraction from Stage 1 (ingestion)."""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    methods: list[str] = Field(default_factory=list)
    results: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    code_references: list[str] = Field(default_factory=list)
    domain: str = "other"
    key_equations: list[str] = Field(default_factory=list)
    model_architecture: str = ""
    contributions: list[str] = Field(default_factory=list)

    @field_validator(
        "authors",
        "methods",
        "results",
        "limitations",
        "datasets",
        "code_references",
        "key_equations",
        "contributions",
        mode="before",
    )
    @classmethod
    def _coerce_list_fields(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if "," in text:
                return [segment.strip() for segment in text.split(",") if segment.strip()]
            return [text]
        if value is None:
            return []
        return [str(value).strip()]


class PaperMetadata(BaseModel):
    """External paper metadata from Semantic Scholar / arXiv."""
    title: str
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    citation_count: int = 0
    venue: str = ""
    url: str = ""


class TokenUsage(BaseModel):
    """Track LLM token consumption for cost control."""
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
    """Non-fatal error from a pipeline stage."""
    stage: str
    message: str
    recoverable: bool = True


class PipelineConfig(BaseModel):
    """User-configurable pipeline parameters."""
    max_seeds: int = Field(
        default=200,
        ge=10,
        le=1000,
        validation_alias=AliasChoices("max_seeds", "maxSeeds"),
    )
    max_cycles: int = Field(
        default=4,
        ge=1,
        le=10,
        validation_alias=AliasChoices("max_cycles", "maxCycles"),
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        validation_alias=AliasChoices("top_k", "topK"),
    )
    budget_limit_usd: float = Field(
        default=5.0,
        ge=0.1,
        validation_alias=AliasChoices("budget_limit_usd", "budgetLimitUsd"),
    )
    seed_dedup_threshold: float = Field(
        default=0.85,
        ge=0.5,
        le=1.0,
        validation_alias=AliasChoices("seed_dedup_threshold", "seedDedupThreshold"),
    )
    tournament_rounds: int = Field(
        default=3,
        ge=1,
        le=10,
        validation_alias=AliasChoices("tournament_rounds", "tournamentRounds"),
    )
    enable_knowledge_graph: bool = True
    enable_evolutionary_ops: bool = True
    domain: str = "other"
    gap_synthesis_iterations: int = Field(
        default=3,
        ge=1,
        le=5,
        validation_alias=AliasChoices("gap_synthesis_iterations", "gapSynthesisIterations"),
    )
    seeds_per_gap: int = Field(
        default=4,
        ge=2,
        le=10,
        validation_alias=AliasChoices("seeds_per_gap", "seedsPerGap"),
    )
    stage_timeouts_seconds: dict[str, int] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("stage_timeouts_seconds", "stageTimeoutsSeconds"),
        description="Optional per-stage timeout overrides (seconds). Keys: ingestion, grounding, overgeneration, filtering, refinement, tournament, portfolio_audit, output.",
    )

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def _normalize_camel_case(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)

        # Common external payload: groundingTimeoutSeconds at config root.
        grounding_timeout = data.pop("groundingTimeoutSeconds", None)
        if grounding_timeout is not None:
            stage_timeouts = data.get("stage_timeouts_seconds") or data.get("stageTimeoutsSeconds") or {}
            if isinstance(stage_timeouts, dict):
                stage_timeouts = dict(stage_timeouts)
                stage_timeouts["grounding"] = grounding_timeout
                data["stage_timeouts_seconds"] = stage_timeouts

        for key in ("enableKnowledgeGraph", "enableEvolutionaryOps"):
            if key in data:
                snake = "enable_knowledge_graph" if key == "enableKnowledgeGraph" else "enable_evolutionary_ops"
                data[snake] = data[key]
        return data

    @field_validator("stage_timeouts_seconds")
    @classmethod
    def _validate_stage_timeouts(cls, value: dict[str, int]) -> dict[str, int]:
        allowed = {
            "ingestion",
            "grounding",
            "overgeneration",
            "filtering",
            "refinement",
            "tournament",
            "portfolio_audit",
            "output",
        }
        sanitized: dict[str, int] = {}
        for raw_key, raw_timeout in (value or {}).items():
            key = str(raw_key).strip().lower()
            if key not in allowed:
                continue
            timeout: int
            try:
                timeout = int(raw_timeout)
            except (TypeError, ValueError):
                continue
            if 10 <= timeout <= 900:
                sanitized[key] = timeout
        return sanitized


# ──────────────────────────────────────────────
# LangGraph Pipeline State
# ──────────────────────────────────────────────

class PipelineState(BaseModel):
    """Central state object passed through the LangGraph pipeline.

    LangGraph requires the state to be a TypedDict or Pydantic model.
    Non-serializable fields (knowledge_graph, vector_store) use Any type.
    """

    # Input
    arxiv_id: str | None = None
    pdf_path: str | None = None
    config: PipelineConfig = Field(default_factory=PipelineConfig)

    # Stage 1: Ingestion
    paper_metadata: PaperMetadata | None = None
    paper_summary: PaperSummary | None = None
    paper_text: str = ""
    text_chunks: list[str] = Field(default_factory=list)
    research_frame: ResearchFrame | None = None

    # Stage 2: Grounding
    related_papers: list[PaperMetadata] = Field(default_factory=list)
    gap_analysis: GapAnalysis | None = None
    meta_gaps: list[MetaGap] = Field(default_factory=list)
    grounding_activity: list[str] = Field(default_factory=list)

    # Stage 3: Overgeneration
    seeds: list[HypothesisSeed] = Field(default_factory=list)

    # Stage 4: Filtering
    filtered_seeds: list[ScoredSeed] = Field(default_factory=list)

    # Stage 5: Refinement — arXiv:2502.18864 debate-evolve loop
    refined_hypotheses: list[EnhancedHypothesis] = Field(default_factory=list)
    elo_ratings: dict[str, float] = Field(default_factory=dict)
    refinement_cycle: int = 0
    meta_review_notes: list[str] = Field(default_factory=list)
    wrong_example_bank: list[FailedSeed] = Field(default_factory=list)

    # Stage 6: Tournament — arXiv:2409.04109 Elo ranking
    tournament_results: list[EnhancedHypothesis] = Field(default_factory=list)

    # Stage 7: Portfolio Audit
    portfolio_audit: PortfolioAudit | None = None

    # Stage 8: Output
    final_output: GeneratorOutput | None = None

    # Infrastructure (non-serializable — excluded from JSON output)
    knowledge_graph: Any = None
    vector_store_client: Any = None
    progress_callback: Any = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    errors: list[StageError] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


# ──────────────────────────────────────────────
# API Request/Response Models
# ──────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """FastAPI request body for /generate endpoint."""
    arxiv_id: str | None = None
    pdf_path: str | None = None
    config: PipelineConfig = Field(default_factory=PipelineConfig)


class ProgressEvent(BaseModel):
    """NDJSON progress event — matches TS PipelineProgressEvent."""
    type: Literal["progress", "warning", "complete", "error"]
    step: str | None = None
    message: str
    current: int | None = None
    total: int | None = None
    data: dict[str, Any] | None = None
