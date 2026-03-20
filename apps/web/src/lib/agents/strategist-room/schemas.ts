import { z } from 'zod';

// ============================================
// Zod Schemas for Strategist Room Agent Outputs
// Runtime validation to catch malformed LLM responses
//
// NOTE: Hypothesis generation schemas are NOT here.
// Hypothesis logic lives in services/hypothesis-room (Python).
// ============================================

// ---- Parser Agent Schema ----

export const PaperAnalysisSchema = z.object({
    title: z.string().min(1, 'Paper title is required'),
    authors: z.array(z.string()).default([]),
    abstract_summary: z.string().min(1, 'Abstract summary is required'),

    equations: z.array(z.object({
        latex: z.string(),
        description: z.string(),
        section: z.string(),
    })).default([]),

    model_architecture: z.object({
        name: z.string(),
        layers: z.array(z.string()).default([]),
        dimensions: z.array(z.string()).default([]),
        hyperparameters: z.record(z.string(), z.string()).default({}),
    }).nullable().default(null),

    datasets: z.array(z.object({
        name: z.string(),
        size: z.string().nullable().default('unknown'),
        source: z.string().nullable().default('unknown'),
    })).default([]),

    metrics: z.array(z.object({
        name: z.string(),
        value: z.string().nullable().default(''),
        comparison: z.string().nullable().default(''),
    })).default([]),

    key_claims: z.array(z.string()).default([]),
    contributions: z.array(z.string()).default([]),
    limitations: z.array(z.string()).default([]),

    domain: z.enum(['cv', 'nlp', 'ml', 'robotics', 'other']).default('other'),

    hallucination_risk: z.object({
        level: z.enum(['low', 'medium', 'high']).default('medium'),
        reasons: z.array(z.string()).default([]),
    }).default({ level: 'medium', reasons: [] }),
});

// ---- Scout Agent Schema ----

const RepoMetricsSchema = z.object({
    stars: z.number().default(0),
    forks: z.number().default(0),
    last_pushed: z.string().default(''),
    days_since_last_push: z.number().default(0),
    health_score: z.number().default(0),
    has_readme: z.boolean().default(false),
    framework: z.string().nullable().default(null),
}).optional();

export const CodePathSchema = z.object({
    path: z.enum(['A', 'B']),

    code_found: z.object({
        urls: z.array(z.string()).default([]),
        primary_repo: z.string(),
        language: z.string(),
        dependencies: z.array(z.string()).default([]),
        technical_debt: z.array(z.string()).default([]),
        reuse_recommendation: z.enum(['reuse', 'partial_reuse', 'rewrite']).default('rewrite'),
        reuse_reasoning: z.string().default(''),
        repo_metrics: RepoMetricsSchema,
        source: z.enum(['paper_text', 'papers_with_code', 'reference_repos']).optional(),
    }).optional(),

    formula_to_code_gap: z.object({
        algorithms_to_implement: z.array(z.object({
            name: z.string(),
            equation_ref: z.string().nullable().default(''),
            complexity: z.enum(['low', 'medium', 'high']).default('medium'),
            suggested_library: z.string(),
            estimated_loc: z.number().default(0),
        })).default([]),
        total_estimated_effort_hours: z.number().default(0),
        required_libraries: z.array(z.string()).default([]),
        adaptable_repos: z.array(z.object({
            url: z.string(),
            paper_title: z.string(),
            relevance: z.string(),
            stars: z.number().default(0),
            framework: z.string().nullable().default(null),
        })).optional(),
    }).optional(),
});

// ---- Accountant Agent Schema ----

export const BudgetQuoteSchema = z.object({
    hypothesis_id: z.string(),

    token_costs: z.object({
        reasoning_tokens: z.number().default(0),
        code_generation_tokens: z.number().default(0),
        verification_tokens: z.number().default(0),
        total_tokens: z.number().default(0),
        rate_per_million: z.number().default(0),
        total_usd: z.number().default(0),
    }),

    compute_costs: z.object({
        gpu_hours: z.number().default(0),
        gpu_type: z.string().default('none'),
        rate_per_hour: z.number().default(0),
        total_usd: z.number().default(0),
    }),

    api_costs: z.object({
        embedding_calls: z.number().default(0),
        llm_calls: z.number().default(0),
        total_usd: z.number().default(0),
    }),

    storage_costs: z.object({
        estimated_gb: z.number().default(0),
        total_usd: z.number().default(0),
    }),

    summary: z.object({
        subtotal_usd: z.number().default(0),
        contingency_percent: z.number().default(10),
        contingency_usd: z.number().default(0),
        total_usd: z.number().default(0),
        min_usd: z.number().default(0),
        max_usd: z.number().default(0),
    }),

    free_tier_compatible: z.boolean().default(false),
    free_tier_warnings: z.array(z.string()).default([]),
});

// ---- Critic Agent Schema ----

export const CriticAssessmentSchema = z.object({
    hypothesis_id: z.string(),
    feasibility_issues: z.array(z.string()).default([]),
    grounding_score: z.number().min(0).max(1).default(0.5),
    overlap_with_literature: z.string().default(''),
    suggested_improvements: z.array(z.string()).default([]),
    verdict: z.enum(['strong', 'viable', 'weak']).default('viable'),
});

export const CriticOutputSchema = z.object({
    assessments: z.array(CriticAssessmentSchema).min(1, 'At least one assessment is required'),
    overall_recommendation: z.string().default(''),
});

// ---- Schema Registry ----

export const AGENT_SCHEMAS: Record<string, z.ZodType> = {
    ParserAgent: PaperAnalysisSchema,
    ScoutAgent: CodePathSchema,
    AccountantAgent: BudgetQuoteSchema,
};
