import { runParserAgent } from './parser-agent';
import { runScoutAgent } from './scout-agent';
import { runBrainstormerAgent } from './brainstormer-agent';
import { runAccountantAgent } from './accountant-agent';
import { createInitialState } from './state';
import { gatherResearchIntelligence } from '@/lib/research-intelligence';
import { logger } from '@/lib/logger';
import type {
    StrategistRoomState,
    StrategistPhase,
    EnhancedResearchManifest,
    RiskAssessment,
} from '@/types/strategist';

/**
 * STAGE 1: Initial Analysis (triggered on PDF upload)
 * Runs Parser -> Research Intelligence -> Scout sequentially.
 * Graceful degradation: Intelligence/Scout failure doesn't block Parser results.
 */
export async function runInitialAnalysis(
    paperContext: string,
    documentId: string,
    conversationId: string,
    userId: string,
    arxivId?: string | null
): Promise<StrategistRoomState> {
    const state = createInitialState(documentId, conversationId, userId);

    // Step 1: Parse
    state.phase = 'parsing';
    try {
        state.paper_analysis = await runParserAgent(paperContext, documentId);
        logger.info('Parser Agent complete', {
            documentId,
            title: state.paper_analysis.title?.substring(0, 80),
            domain: state.paper_analysis.domain,
        });
    } catch (error) {
        state.phase = 'error';
        state.errors.push({
            phase: 'parsing' as StrategistPhase,
            message: error instanceof Error ? error.message : String(error),
            timestamp: new Date().toISOString(),
        });
        logger.error('Parser Agent failed', error instanceof Error ? error : new Error(String(error)), { documentId });
        state.updated_at = new Date().toISOString();
        return state;
    }

    // Step 2: Research Intelligence (non-fatal)
    state.phase = 'gathering_intelligence';
    try {
        const s2Id = arxivId ? `ArXiv:${arxivId}` : null;
        state.research_intelligence = await gatherResearchIntelligence(
            state.paper_analysis,
            arxivId || null,
            s2Id
        );
        logger.info('Research Intelligence complete', {
            documentId,
            repos: state.research_intelligence.code_discovery.total_repos_found,
            references: state.research_intelligence.citation_graph.reference_count,
            relatedPapers: state.research_intelligence.related_work.papers.length,
            errors: state.research_intelligence.errors.length,
        });
    } catch (error) {
        // Research Intelligence failure is non-fatal
        state.errors.push({
            phase: 'gathering_intelligence' as StrategistPhase,
            message: error instanceof Error ? error.message : String(error),
            timestamp: new Date().toISOString(),
        });
        logger.warn('Research Intelligence failed (non-fatal)', {
            documentId,
            error: error instanceof Error ? error.message : String(error),
        });
    }

    // Step 3: Scout (with real data if available)
    state.phase = 'scouting';
    try {
        state.code_path = await runScoutAgent(
            paperContext,
            state.paper_analysis,
            documentId,
            state.research_intelligence
        );
        logger.info('Scout Agent complete', {
            documentId,
            path: state.code_path.path,
            hasRepoMetrics: !!state.code_path.code_found?.repo_metrics,
        });
    } catch (error) {
        // Scout failure is non-fatal — we still have parser results
        state.errors.push({
            phase: 'scouting' as StrategistPhase,
            message: error instanceof Error ? error.message : String(error),
            timestamp: new Date().toISOString(),
        });
        logger.warn('Scout Agent failed (non-fatal)', {
            documentId,
            error: error instanceof Error ? error.message : String(error),
        });
    }

    state.phase = 'analysis_complete';
    state.updated_at = new Date().toISOString();
    return state;
}

/**
 * STAGE 2: Hypothesis Generation (triggered by user message)
 * Runs Brainstormer with user input, previous context, AND research intelligence.
 * Supports iterative refinement.
 */
export async function runHypothesisGeneration(
    state: StrategistRoomState,
    paperContext: string,
    userMessage: string
): Promise<StrategistRoomState> {
    if (!state.paper_analysis) {
        throw new Error('Cannot brainstorm without paper analysis. Run initial analysis first.');
    }

    state.phase = 'brainstorming';
    state.user_refinement_history.push({
        message: userMessage,
        timestamp: new Date().toISOString(),
    });

    try {
        state.brainstormer_output = await runBrainstormerAgent(
            paperContext,
            state.paper_analysis,
            state.code_path || { path: 'B', formula_to_code_gap: { algorithms_to_implement: [], total_estimated_effort_hours: 0, required_libraries: [] } },
            userMessage,
            state.brainstormer_output,
            state.user_refinement_history,
            state.document_id,
            state.research_intelligence
        );
        logger.info('Brainstormer Agent complete', {
            documentId: state.document_id,
            hypothesesCount: state.brainstormer_output.hypotheses.length,
        });
    } catch (error) {
        state.phase = 'error';
        state.errors.push({
            phase: 'brainstorming' as StrategistPhase,
            message: error instanceof Error ? error.message : String(error),
            timestamp: new Date().toISOString(),
        });
        logger.error('Brainstormer Agent failed', error instanceof Error ? error : new Error(String(error)), {
            documentId: state.document_id,
        });
        state.updated_at = new Date().toISOString();
        return state;
    }

    state.phase = 'hypothesis_presented';
    state.updated_at = new Date().toISOString();
    return state;
}

/**
 * STAGE 3: Budget Estimation (triggered when user selects a hypothesis)
 */
export async function runBudgetEstimation(
    state: StrategistRoomState,
    hypothesisId: string
): Promise<StrategistRoomState> {
    if (!state.brainstormer_output || !state.paper_analysis) {
        throw new Error('Cannot estimate budget without hypothesis and analysis.');
    }

    const selected = state.brainstormer_output.hypotheses.find(h => h.id === hypothesisId);
    if (!selected) {
        throw new Error(`Hypothesis not found: ${hypothesisId}`);
    }

    state.selected_hypothesis_id = hypothesisId;
    state.phase = 'budgeting';

    try {
        state.budget_quote = await runAccountantAgent(
            state.paper_analysis,
            state.code_path || { path: 'B', formula_to_code_gap: { algorithms_to_implement: [], total_estimated_effort_hours: 0, required_libraries: [] } },
            selected,
            state.document_id
        );
        logger.info('Accountant Agent complete', {
            documentId: state.document_id,
            totalUsd: state.budget_quote.summary.total_usd,
            freeTierCompatible: state.budget_quote.free_tier_compatible,
        });
    } catch (error) {
        state.phase = 'error';
        state.errors.push({
            phase: 'budgeting' as StrategistPhase,
            message: error instanceof Error ? error.message : String(error),
            timestamp: new Date().toISOString(),
        });
        logger.error('Accountant Agent failed', error instanceof Error ? error : new Error(String(error)), {
            documentId: state.document_id,
        });
        state.updated_at = new Date().toISOString();
        return state;
    }

    state.phase = 'budget_presented';
    state.updated_at = new Date().toISOString();
    return state;
}

/**
 * STAGE 4: Finalize and generate Enhanced Research Manifest.
 * Called when user approves the budget.
 */
export function finalizeManifest(
    state: StrategistRoomState
): EnhancedResearchManifest {
    if (!state.paper_analysis || !state.code_path || !state.budget_quote || !state.selected_hypothesis_id || !state.brainstormer_output) {
        throw new Error('Cannot finalize manifest: incomplete state.');
    }

    const hypothesis = state.brainstormer_output.hypotheses.find(
        h => h.id === state.selected_hypothesis_id
    );
    if (!hypothesis) {
        throw new Error(`Selected hypothesis not found: ${state.selected_hypothesis_id}`);
    }

    const riskAssessment: RiskAssessment = {
        hallucination_risk: state.paper_analysis.hallucination_risk.level,
        feasibility_score: hypothesis.feasibility_score,
        confidence_score: hypothesis.confidence,
        risks: [
            ...(state.paper_analysis.hallucination_risk.level !== 'low'
                ? [{
                    category: 'Hallucination',
                    description: state.paper_analysis.hallucination_risk.reasons.join('; '),
                    severity: state.paper_analysis.hallucination_risk.level as 'low' | 'medium' | 'high',
                    mitigation: 'Cross-reference with original paper. Verify equations and metrics.',
                }]
                : []),
            ...(!state.budget_quote.free_tier_compatible
                ? [{
                    category: 'Budget',
                    description: state.budget_quote.free_tier_warnings.join('; '),
                    severity: 'medium' as const,
                    mitigation: 'Consider scaling down the experiment or using CPU-only approach.',
                }]
                : []),
        ],
    };

    // Build execution plan based on code path and hypothesis
    const executionSteps = state.code_path.path === 'A'
        ? [
            { order: 1, description: 'Clone and assess existing repository', agent: 'Coder', estimated_tokens: 1000, dependencies: [] },
            { order: 2, description: 'Install dependencies and verify base code runs', agent: 'Coder', estimated_tokens: 2000, dependencies: [1] },
            { order: 3, description: `Apply modifications: ${hypothesis.required_modifications.join(', ')}`, agent: 'Coder', estimated_tokens: 5000, dependencies: [2] },
            { order: 4, description: 'Execute modified experiment', agent: 'Coder', estimated_tokens: 3000, dependencies: [3] },
            { order: 5, description: 'Verify results against hypothesis predictions', agent: 'Verifier', estimated_tokens: 2000, dependencies: [4] },
        ]
        : [
            { order: 1, description: 'Generate experiment code from scratch based on paper equations', agent: 'Coder', estimated_tokens: 8000, dependencies: [] },
            { order: 2, description: 'Install required libraries and set up environment', agent: 'Coder', estimated_tokens: 1000, dependencies: [1] },
            { order: 3, description: `Apply hypothesis modifications: ${hypothesis.required_modifications.join(', ')}`, agent: 'Coder', estimated_tokens: 3000, dependencies: [2] },
            { order: 4, description: 'Execute experiment in sandbox', agent: 'Coder', estimated_tokens: 3000, dependencies: [3] },
            { order: 5, description: 'Verify results against hypothesis predictions', agent: 'Verifier', estimated_tokens: 2000, dependencies: [4] },
        ];

    state.risk_assessment = riskAssessment;
    state.approved = true;
    state.phase = 'approved';
    state.updated_at = new Date().toISOString();

    logger.info('Manifest finalized', {
        sessionId: state.session_id,
        documentId: state.document_id,
        hypothesisId: hypothesis.id,
    });

    return {
        paper_analysis: state.paper_analysis,
        code_path: state.code_path,
        hypothesis,
        refinement_history: state.user_refinement_history,
        budget: state.budget_quote,
        execution_plan: {
            steps: executionSteps,
            total_estimated_time_minutes: Math.ceil(
                executionSteps.reduce((sum, s) => sum + s.estimated_tokens, 0) / 1000
            ),
        },
        risk_assessment: riskAssessment,
        anti_gravity_check: {
            passed: state.paper_analysis.hallucination_risk.level !== 'high',
            violations: state.paper_analysis.hallucination_risk.level === 'high'
                ? state.paper_analysis.hallucination_risk.reasons
                : [],
        },
        session_id: state.session_id,
        document_id: state.document_id,
        created_at: new Date().toISOString(),
    };
}
