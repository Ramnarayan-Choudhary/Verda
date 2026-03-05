// ============================================
// VREDA.ai Strategist Room Type Definitions
// ============================================

// ---- Parser Agent Output ----

export interface PaperAnalysis {
    title: string;
    authors: string[];
    abstract_summary: string;

    equations: {
        latex: string;
        description: string;
        section: string;
    }[];

    model_architecture: {
        name: string;
        layers: string[];
        dimensions: string[];
        hyperparameters: Record<string, string>;
    } | null;

    datasets: {
        name: string;
        size: string;
        source: string;
    }[];

    metrics: {
        name: string;
        value: string;
        comparison: string;
    }[];

    key_claims: string[];
    contributions: string[];
    limitations: string[];

    domain: 'cv' | 'nlp' | 'ml' | 'robotics' | 'other';

    hallucination_risk: {
        level: 'low' | 'medium' | 'high';
        reasons: string[];
    };
}

// ---- Scout Agent Output ----

export interface CodePathAssessment {
    path: 'A' | 'B';

    /** Path A: code/repo found in paper */
    code_found?: {
        urls: string[];
        primary_repo: string;
        language: string;
        dependencies: string[];
        technical_debt: string[];
        reuse_recommendation: 'reuse' | 'partial_reuse' | 'rewrite';
        reuse_reasoning: string;
        repo_metrics?: {
            stars: number;
            forks: number;
            last_pushed: string;
            days_since_last_push: number;
            health_score: number;
            has_readme: boolean;
            framework: string | null;
        };
        source?: 'paper_text' | 'papers_with_code' | 'reference_repos';
    };

    /** Path B: no code found — formula-to-code gap */
    formula_to_code_gap?: {
        algorithms_to_implement: {
            name: string;
            equation_ref: string;
            complexity: 'low' | 'medium' | 'high';
            suggested_library: string;
            estimated_loc: number;
        }[];
        total_estimated_effort_hours: number;
        required_libraries: string[];
        adaptable_repos?: {
            url: string;
            paper_title: string;
            relevance: string;
            stars: number;
            framework: string | null;
        }[];
    };
}

// ---- Brainstormer Agent Output ----

export interface Hypothesis {
    id: string;
    type: 'scale' | 'modality_shift' | 'architecture_ablation';
    title: string;
    description: string;
    testable_prediction: string;
    expected_outcome: string;
    feasibility_score: number;
    confidence: number;
    required_modifications: string[];
    estimated_complexity: 'low' | 'medium' | 'high';

    evidence_basis?: {
        supporting_papers: {
            title: string;
            arxiv_id: string | null;
            year: number | null;
            citation_count: number;
            relevance: string;
        }[];
        prior_results?: string;
        key_insight: string;
    };

    novelty_assessment?: {
        is_novel: boolean;
        similar_work: string[];
        what_is_new: string;
        novelty_score: number;
    };

    experiment_design?: import('./research-intelligence').ExperimentDesign;

    critic_assessment?: CriticAssessment;
}

export interface BrainstormerOutput {
    hypotheses: Hypothesis[];
    reasoning_context: string;
}

// ---- Critic Agent Output ----

export interface CriticAssessment {
    hypothesis_id: string;
    feasibility_issues: string[];
    grounding_score: number;
    overlap_with_literature: string;
    suggested_improvements: string[];
    verdict: 'strong' | 'viable' | 'weak';
}

export interface CriticOutput {
    assessments: CriticAssessment[];
    overall_recommendation: string;
}

// ---- Accountant Agent Output ----

export interface BudgetQuote {
    hypothesis_id: string;

    token_costs: {
        reasoning_tokens: number;
        code_generation_tokens: number;
        verification_tokens: number;
        total_tokens: number;
        rate_per_million: number;
        total_usd: number;
    };

    compute_costs: {
        gpu_hours: number;
        gpu_type: string;
        rate_per_hour: number;
        total_usd: number;
    };

    api_costs: {
        embedding_calls: number;
        llm_calls: number;
        total_usd: number;
    };

    storage_costs: {
        estimated_gb: number;
        total_usd: number;
    };

    summary: {
        subtotal_usd: number;
        contingency_percent: number;
        contingency_usd: number;
        total_usd: number;
        min_usd: number;
        max_usd: number;
    };

    free_tier_compatible: boolean;
    free_tier_warnings: string[];
}

// ---- Risk Assessment ----

export interface RiskAssessment {
    hallucination_risk: 'low' | 'medium' | 'high';
    feasibility_score: number;
    confidence_score: number;
    risks: {
        category: string;
        description: string;
        severity: 'low' | 'medium' | 'high';
        mitigation: string;
    }[];
}

// ---- State Management ----

export type StrategistPhase =
    | 'idle'
    | 'parsing'
    | 'gathering_intelligence'
    | 'scouting'
    | 'analysis_complete'
    | 'brainstorming'
    | 'hypothesis_presented'
    | 'budgeting'
    | 'budget_presented'
    | 'approved'
    | 'error';

export interface StrategistRoomState {
    session_id: string;
    document_id: string;
    conversation_id: string;
    user_id: string;
    arxiv_id?: string | null;
    hypothesis_engine_preference?: 'gpt' | 'claude';
    last_hypothesis_engine_used?: 'gpt' | 'claude' | 'legacy' | null;

    phase: StrategistPhase;

    // Phase 1: Initial analysis (runs on upload)
    paper_analysis: PaperAnalysis | null;
    research_intelligence: import('./research-intelligence').ResearchIntelligence | null;
    code_path: CodePathAssessment | null;

    // Phase 2: Hypothesis generation (user-triggered)
    brainstormer_output: BrainstormerOutput | null;
    critic_output: CriticOutput | null;
    /** Full pipeline output from the Python hypothesis service */
    hypothesis_pipeline_output: GeneratorOutput | null;
    user_refinement_history: {
        message: string;
        timestamp: string;
    }[];
    selected_hypothesis_id: string | null;

    // Phase 3: Budget (auto-triggered on hypothesis selection)
    budget_quote: BudgetQuote | null;

    // Phase 4: Final manifest (user approves)
    risk_assessment: RiskAssessment | null;
    approved: boolean;

    // Metadata
    created_at: string;
    updated_at: string;
    errors: {
        phase: StrategistPhase;
        message: string;
        timestamp: string;
    }[];
}

// ---- Enhanced Hypothesis Types (rendered from Python service output) ----

export interface DimensionScores {
    novelty: number;
    feasibility: number;
    impact: number;
    grounding: number;
    testability: number;
    clarity: number;
}

export interface EnhancedHypothesis {
    id: string;
    type: string;
    title: string;
    description: string;
    short_hypothesis: string;
    testable_prediction: string;
    expected_outcome: string;
    scores: DimensionScores;
    composite_score: number;
    required_modifications: string[];
    estimated_complexity: 'low' | 'medium' | 'high';
    evidence_basis: {
        supporting_papers: {
            title: string;
            arxiv_id: string | null;
            year: number | null;
            citation_count: number;
            relevance: string;
        }[];
        prior_results: string;
        key_insight: string;
        gap_exploited: string;
    };
    novelty_assessment: {
        is_novel: boolean;
        similar_work: string[];
        what_is_new: string;
        novelty_score: number;
        novelty_type: string;
    };
    experiment_design?: import('./research-intelligence').ExperimentDesign;
    risk_factors: string[];
    related_work_summary: string;
    addresses_gap_id: string | null;
    critic_assessment?: CriticAssessment;
    reflection_rounds_completed: number;
}

export interface GeneratorOutput {
    hypotheses: EnhancedHypothesis[];
    reasoning_context: string;
    gap_analysis_used: boolean;
    reflection_rounds: number;
    generation_strategy: 'knowledge_grounded' | 'prompt_based';
    engine_used?: 'gpt' | 'claude' | 'legacy';
}

// ---- Enhanced Research Manifest (Final Output) ----

export interface EnhancedResearchManifest {
    paper_analysis: PaperAnalysis;
    code_path: CodePathAssessment;

    hypothesis: Hypothesis;
    refinement_history: { message: string; timestamp: string }[];

    budget: BudgetQuote;

    execution_plan: {
        steps: {
            order: number;
            description: string;
            agent: string;
            estimated_tokens: number;
            dependencies: number[];
        }[];
        total_estimated_time_minutes: number;
    };

    risk_assessment: RiskAssessment;

    anti_gravity_check: {
        passed: boolean;
        violations: string[];
    };

    session_id: string;
    document_id: string;
    created_at: string;
}
