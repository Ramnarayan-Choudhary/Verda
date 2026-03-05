import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { createAdminSupabaseClient } from '@/lib/supabase/admin';
import { runInitialAnalysis } from '@/lib/agents/strategist-room';
import { validateUUID, validateMessage } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { config } from '@/lib/config';
import { logger } from '@/lib/logger';
import type { StrategistRoomState, BrainstormerOutput, GeneratorOutput, CriticOutput } from '@/types/strategist';
import { appendQuestEvent } from '@/lib/quest-events';
import { isArxivId, normalizeArxivId } from '@/lib/literature/arxiv';

export const maxDuration = 300; // 5 minutes — Python service needs time for 8 stages

type HypothesisEngine = 'gpt' | 'claude';

// ─── Python Service Types ───────────────────────────────

interface PythonProgressEvent {
    type: 'progress' | 'warning' | 'complete' | 'error';
    step: string | null;
    message: string;
    current: number | null;
    total: number | null;
    data: Record<string, unknown> | null;
}

interface PythonHypothesis {
    id: string;
    type: string;
    title: string;
    description: string;
    short_hypothesis: string;
    testable_prediction: string;
    expected_outcome: string;
    scores: {
        novelty: number;
        feasibility: number;
        impact: number;
        grounding: number;
        testability: number;
        clarity: number;
    };
    composite_score: number;
    required_modifications: string[];
    estimated_complexity: 'low' | 'medium' | 'high';
    evidence_basis: {
        supporting_papers: { title: string; arxiv_id: string | null; year: number | null; citation_count: number; relevance: string }[];
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
    experiment_design: Record<string, unknown>;
    risk_factors: string[];
    related_work_summary: string;
    addresses_gap_id: string | null;
    critic_assessment: {
        hypothesis_id: string;
        feasibility_issues: string[];
        grounding_score: number;
        overlap_with_literature: string;
        suggested_improvements: string[];
        verdict: 'strong' | 'viable' | 'weak';
    } | null;
    reflection_rounds_completed: number;
    archetype: string;
    statement: string;
    mve: string[];
    falsification_threshold: string;
    portfolio_tag: string;
    elo_rating: number;
}

interface PythonGeneratorOutput {
    hypotheses: PythonHypothesis[];
    reasoning_context: string;
    gap_analysis_used: boolean;
    reflection_rounds: number;
    generation_strategy: string;
    engine_used?: 'gpt' | 'claude' | 'legacy';
    portfolio_audit: {
        coverage: Record<string, string>;
        redundancies: string[];
        execution_order: string[];
    } | null;
}

interface HypothesisServiceInput {
    arxivId?: string;
    pdfPath?: string;
}

interface HypothesisServiceOptions {
    topK?: number;
}

interface NormalizedHypothesis {
    id: string;
    type: string;
    title: string;
    description: string;
    short_hypothesis: string;
    testable_prediction: string;
    expected_outcome: string;
    scores: PythonHypothesis['scores'];
    composite_score: number;
    required_modifications: string[];
    estimated_complexity: 'low' | 'medium' | 'high';
    evidence_basis: PythonHypothesis['evidence_basis'];
    novelty_assessment: PythonHypothesis['novelty_assessment'];
    risk_factors: string[];
    related_work_summary: string;
    addresses_gap_id: string | null;
    critic_assessment: PythonHypothesis['critic_assessment'];
    reflection_rounds_completed: number;
    statement: string;
    elo_rating: number;
}

function inferRequestedHypothesisCount(message: string): number | null {
    const text = message.toLowerCase();
    const patterns = [
        /\b(\d{1,2})\s+(?:new|novel|strong|good|best)?\s*hypotheses?\b/,
        /\bhypotheses?\s*[:\-]?\s*(\d{1,2})\b/,
        /\bbrainstorm\s+(\d{1,2})\b/,
    ];
    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (!match) continue;
        const parsed = Number.parseInt(match[1], 10);
        if (Number.isFinite(parsed) && parsed >= 1 && parsed <= 10) {
            return parsed;
        }
    }
    return null;
}

async function ensureHypothesisServiceReady(
    serviceUrl: string,
    engine: HypothesisEngine
): Promise<{ ready: boolean; detail?: string }> {
    try {
        const response = await fetch(`${serviceUrl}/healthz`, {
            signal: AbortSignal.timeout(3000),
        });
        if (!response.ok) {
            return { ready: false, detail: `healthz returned ${response.status}` };
        }
        const payload = await response.json().catch(() => ({} as Record<string, unknown>));
        const status = typeof payload.status === 'string' ? payload.status : '';
        if (status !== 'ok') {
            return { ready: false, detail: `${engine.toUpperCase()} hypothesis service health status is not ok.` };
        }
        return { ready: true };
    } catch (error) {
        const detail = error instanceof Error ? error.message : 'service did not respond on /healthz';
        return { ready: false, detail };
    }
}

// ─── Call Python Service ────────────────────────────────

async function callHypothesisService(
    input: HypothesisServiceInput,
    domain: string,
    serviceUrl: string,
    engine: HypothesisEngine,
    options?: HypothesisServiceOptions
): Promise<PythonGeneratorOutput> {
    const url = `${serviceUrl}/generate`;
    const groundingTimeoutSeconds = Math.max(120, Math.min(config.hypothesisService.groundingTimeoutSeconds, 900));
    const topK = Math.max(1, Math.min(options?.topK ?? 5, 10));
    const maxSeeds = Math.max(24, Math.min(topK * 8, 120));
    const maxCycles = topK >= 4 ? 3 : 2;

    logger.info('Calling hypothesis service', {
        url,
        arxivId: input.arxivId || null,
        pdfPath: input.pdfPath || null,
        domain,
        topK,
        maxSeeds,
        maxCycles,
        groundingTimeoutSeconds,
    });

    const requestConfig: Record<string, unknown> = {
        domain,
        stage_timeouts_seconds: {
            grounding: groundingTimeoutSeconds,
        },
    };

    if (engine === 'claude') {
        const portfolioSafeSlots = topK >= 5 ? 2 : 1;
        const portfolioMoonshotSlots = topK >= 5 ? 1 : 0;
        const portfolioMediumSlots = Math.max(1, topK - portfolioSafeSlots - portfolioMoonshotSlots);
        requestConfig.max_hypotheses_per_strategy = topK <= 4 ? 2 : 3;
        requestConfig.tribunal_cycles = topK <= 4 ? 2 : 3;
        requestConfig.max_concurrent_strategies = 2;
        requestConfig.max_concurrent_critics = 1;
        requestConfig.portfolio_safe_slots = portfolioSafeSlots;
        requestConfig.portfolio_medium_slots = portfolioMediumSlots;
        requestConfig.portfolio_moonshot_slots = portfolioMoonshotSlots;
    } else {
        requestConfig.max_seeds = maxSeeds;
        requestConfig.max_cycles = maxCycles;
        requestConfig.top_k = topK;
    }

    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            arxiv_id: input.arxivId ?? null,
            pdf_path: input.pdfPath ?? null,
            config: requestConfig,
        }),
    });

    if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new Error(`Hypothesis service returned ${response.status}: ${errorText}`);
    }

    // Parse NDJSON streaming response
    const text = await response.text();
    const lines = text.trim().split('\n').filter(Boolean);

    let finalOutput: PythonGeneratorOutput | null = null;
    const progressTrace: string[] = [];

    for (const line of lines) {
        try {
            const event: PythonProgressEvent = JSON.parse(line);

            if (event.type === 'progress' || event.type === 'warning') {
                logger.info('hypothesis_service.progress', {
                    step: event.step,
                    message: event.message,
                    progress: event.current && event.total ? `${event.current}/${event.total}` : undefined,
                    data: event.data ?? undefined,
                });
                const eventData =
                    event.data && Object.keys(event.data).length > 0
                        ? ` data=${JSON.stringify(event.data).slice(0, 500)}`
                        : '';
                progressTrace.push(`[${event.step || 'pipeline'}] ${event.message}${eventData}`);
            } else if (event.type === 'complete' && event.data) {
                const wrapped = event.data as { output?: unknown };
                const outputPayload = wrapped.output ?? event.data;
                if (outputPayload && typeof outputPayload === 'object') {
                    finalOutput = outputPayload as PythonGeneratorOutput;
                }
            } else if (event.type === 'error') {
                throw new Error(`Hypothesis service error at ${event.step}: ${event.message}`);
            }
        } catch (parseError) {
            if (parseError instanceof SyntaxError) {
                logger.warn('hypothesis_service.parse_error', { line: line.substring(0, 200) });
                continue;
            }
            throw parseError;
        }
    }

    if (!finalOutput) {
        throw new Error('Hypothesis service completed without returning output');
    }
    if (Array.isArray(finalOutput.hypotheses) && finalOutput.hypotheses.length > topK) {
        finalOutput.hypotheses = finalOutput.hypotheses.slice(0, topK);
    }
    if (progressTrace.length > 0) {
        const traceBlock = `Pipeline trace: ${progressTrace.slice(-12).join(' || ')}`;
        finalOutput.reasoning_context = finalOutput.reasoning_context
            ? `${finalOutput.reasoning_context} | ${traceBlock}`
            : traceBlock;
    }

    return finalOutput;
}

// ─── Map Python Output → Frontend Format ────────────────

function readString(value: unknown, fallback = ''): string {
    return typeof value === 'string' ? value : fallback;
}

function readNumber(value: unknown, fallback: number): number {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string') {
        const parsed = Number.parseFloat(value);
        if (Number.isFinite(parsed)) return parsed;
    }
    return fallback;
}

function readStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) return [];
    return value.map(item => String(item).trim()).filter(Boolean);
}

function clampPercent(value: number): number {
    return Math.max(0, Math.min(100, Math.round(value)));
}

function truncateText(value: string, maxLen: number): string {
    if (value.length <= maxLen) return value;
    return `${value.slice(0, Math.max(0, maxLen - 1)).trimEnd()}…`;
}

function normalizeComplexity(value: unknown): 'low' | 'medium' | 'high' {
    if (value === 'low' || value === 'medium' || value === 'high') return value;
    const text = readString(value, '').toLowerCase();
    if (!text) return 'medium';
    if (text.includes('day') || text.includes('quick') || text.includes('simple')) return 'low';
    if (text.includes('month') || text.includes('hard') || text.includes('complex')) return 'high';
    return 'medium';
}

function normalizeHypothesis(hypothesis: PythonHypothesis, index: number): NormalizedHypothesis {
    const raw = hypothesis as unknown as Record<string, unknown>;
    const title = readString(raw.title, `Hypothesis ${index + 1}`);
    const condition = readString(raw.condition);
    const intervention = readString(raw.intervention);
    const mechanism = readString(raw.mechanism);
    const prediction = readString(raw.prediction);

    const descriptionParts = [
        readString(raw.description),
        readString(raw.short_hypothesis),
        readString(raw.statement),
        [condition, intervention, mechanism].filter(Boolean).join(' | '),
    ].filter(Boolean);
    const description = descriptionParts[0] || title;

    const shortHypothesis = readString(raw.short_hypothesis, description);
    const minimalTest =
        raw.minimal_test && typeof raw.minimal_test === 'object'
            ? raw.minimal_test as Record<string, unknown>
            : null;
    const minimalTestPlan = minimalTest
        ? [readString(minimalTest.dataset), readString(minimalTest.baseline), readString(minimalTest.primary_metric)]
            .filter(Boolean)
            .join(' | ')
        : '';
    const testablePrediction =
        readString(raw.testable_prediction) ||
        prediction ||
        minimalTestPlan ||
        readString(raw.falsification_criterion, 'Run the minimal test and check the primary metric.');
    const expectedOutcome =
        readString(raw.expected_outcome) ||
        readString(raw.expected_outcome_if_true) ||
        readString(raw.success_definition, 'Measure against the stated success threshold.');

    const panelCompositeRaw = readNumber(raw.panel_composite, Number.NaN);
    const panelCompositePercent = Number.isFinite(panelCompositeRaw)
        ? (panelCompositeRaw <= 10 ? panelCompositeRaw * 10 : panelCompositeRaw)
        : Number.NaN;
    const fallbackScore = Number.isFinite(panelCompositePercent) ? clampPercent(panelCompositePercent) : 50;
    const rawScores = raw.scores as Partial<PythonHypothesis['scores']> | undefined;
    const scores: PythonHypothesis['scores'] = {
        novelty: clampPercent(readNumber(rawScores?.novelty, fallbackScore)),
        feasibility: clampPercent(readNumber(rawScores?.feasibility, fallbackScore)),
        impact: clampPercent(readNumber(rawScores?.impact, fallbackScore)),
        grounding: clampPercent(readNumber(rawScores?.grounding, fallbackScore)),
        testability: clampPercent(readNumber(rawScores?.testability, fallbackScore)),
        clarity: clampPercent(readNumber(rawScores?.clarity, fallbackScore)),
    };

    const compositeScore = clampPercent(
        readNumber(
            raw.composite_score,
            Number.isFinite(panelCompositePercent)
                ? panelCompositePercent
                : (scores.novelty + scores.feasibility + scores.impact + scores.grounding + scores.testability + scores.clarity) / 6
        )
    );

    const supportingPapersRaw = raw.evidence_basis && typeof raw.evidence_basis === 'object'
        ? (raw.evidence_basis as Record<string, unknown>).supporting_papers
        : undefined;
    const supportingPapers = Array.isArray(supportingPapersRaw)
        ? supportingPapersRaw
            .filter(item => item && typeof item === 'object')
            .map(item => {
                const paper = item as Record<string, unknown>;
                return {
                    title: readString(paper.title, 'Unknown paper'),
                    arxiv_id: readString(paper.arxiv_id) || null,
                    year: Number.isFinite(readNumber(paper.year, Number.NaN)) ? readNumber(paper.year, Number.NaN) : null,
                    citation_count: Math.max(0, Math.round(readNumber(paper.citation_count, 0))),
                    relevance: readString(paper.relevance, ''),
                };
            })
        : [];

    const evidence_basis: PythonHypothesis['evidence_basis'] = {
        supporting_papers: supportingPapers,
        prior_results: raw.evidence_basis && typeof raw.evidence_basis === 'object'
            ? readString((raw.evidence_basis as Record<string, unknown>).prior_results)
            : '',
        key_insight: raw.evidence_basis && typeof raw.evidence_basis === 'object'
            ? readString((raw.evidence_basis as Record<string, unknown>).key_insight)
            : '',
        gap_exploited: raw.evidence_basis && typeof raw.evidence_basis === 'object'
            ? readString((raw.evidence_basis as Record<string, unknown>).gap_exploited)
            : readString(raw.source_gap_id),
    };

    const noveltyAssessmentRaw = raw.novelty_assessment && typeof raw.novelty_assessment === 'object'
        ? raw.novelty_assessment as Record<string, unknown>
        : null;
    const novelty_assessment: PythonHypothesis['novelty_assessment'] = {
        is_novel: noveltyAssessmentRaw
            ? Boolean(noveltyAssessmentRaw.is_novel ?? true)
            : true,
        similar_work: noveltyAssessmentRaw
            ? readStringArray(noveltyAssessmentRaw.similar_work)
            : [],
        what_is_new: noveltyAssessmentRaw
            ? readString(noveltyAssessmentRaw.what_is_new, readString(raw.novelty_claim))
            : readString(raw.novelty_claim),
        novelty_score: clampPercent(noveltyAssessmentRaw ? readNumber(noveltyAssessmentRaw.novelty_score, scores.novelty) : scores.novelty),
        novelty_type: noveltyAssessmentRaw
            ? readString(noveltyAssessmentRaw.novelty_type, 'new_application')
            : 'new_application',
    };

    return {
        id: readString(raw.id, `hyp-${index + 1}`),
        type: readString(raw.type, readString(raw.generation_strategy, 'combination')),
        title,
        description: truncateText(description, 420),
        short_hypothesis: truncateText(shortHypothesis, 220),
        testable_prediction: truncateText(testablePrediction, 320),
        expected_outcome: expectedOutcome,
        scores,
        composite_score: compositeScore,
        required_modifications: readStringArray(raw.required_modifications),
        estimated_complexity: normalizeComplexity(raw.estimated_complexity || raw.suggested_timeline),
        evidence_basis,
        novelty_assessment,
        risk_factors: readStringArray(raw.risk_factors).length > 0
            ? readStringArray(raw.risk_factors)
            : readStringArray(raw.dependencies),
        related_work_summary: readString(raw.related_work_summary, readString(raw.closest_existing_work)),
        addresses_gap_id: readString(raw.addresses_gap_id) || readString(raw.source_gap_id) || null,
        critic_assessment: raw.critic_assessment && typeof raw.critic_assessment === 'object'
            ? raw.critic_assessment as PythonHypothesis['critic_assessment']
            : null,
        reflection_rounds_completed: Math.max(0, Math.round(readNumber(raw.reflection_rounds_completed, 0))),
        statement: readString(raw.statement, [condition, intervention, prediction].filter(Boolean).join(' ')),
        elo_rating: readNumber(raw.elo_rating, 1400 + compositeScore * 2),
    };
}

function mapPythonToFrontend(pythonOutput: PythonGeneratorOutput): {
    brainstormer_output: BrainstormerOutput;
    hypothesis_pipeline_output: GeneratorOutput;
    critic_output: CriticOutput;
} {
    const normalizedHypotheses = pythonOutput.hypotheses.map((h, idx) => normalizeHypothesis(h, idx));
    const generationStrategy: GeneratorOutput['generation_strategy'] =
        pythonOutput.generation_strategy === 'prompt_based' ? 'prompt_based' : 'knowledge_grounded';

    const brainstormer_output: BrainstormerOutput = {
        hypotheses: normalizedHypotheses.map(h => ({
            id: h.id,
            type: mapHypothesisType(h.type),
            title: h.title,
            description: h.description,
            testable_prediction: h.testable_prediction,
            expected_outcome: h.expected_outcome,
            feasibility_score: (h.scores.feasibility ?? 50) / 100,
            confidence: (h.scores.grounding ?? 50) / 100,
            required_modifications: h.required_modifications,
            estimated_complexity: h.estimated_complexity,
            evidence_basis: {
                supporting_papers: h.evidence_basis.supporting_papers,
                prior_results: h.evidence_basis.prior_results,
                key_insight: h.evidence_basis.key_insight,
            },
            novelty_assessment: {
                is_novel: h.novelty_assessment.is_novel,
                similar_work: h.novelty_assessment.similar_work,
                what_is_new: h.novelty_assessment.what_is_new,
                novelty_score: h.novelty_assessment.novelty_score / 100,
            },
            experiment_design: undefined,
            critic_assessment: h.critic_assessment || undefined,
        })),
        reasoning_context: pythonOutput.reasoning_context,
    };

    const hypothesis_pipeline_output: GeneratorOutput = {
        hypotheses: normalizedHypotheses.map(h => ({
            id: h.id,
            type: h.type,
            title: h.title,
            description: h.description,
            short_hypothesis: h.short_hypothesis,
            testable_prediction: h.testable_prediction,
            expected_outcome: h.expected_outcome,
            scores: h.scores,
            composite_score: h.composite_score,
            required_modifications: h.required_modifications,
            estimated_complexity: h.estimated_complexity,
            evidence_basis: h.evidence_basis,
            novelty_assessment: h.novelty_assessment,
            risk_factors: h.risk_factors,
            related_work_summary: h.related_work_summary,
            addresses_gap_id: h.addresses_gap_id,
            reflection_rounds_completed: h.reflection_rounds_completed,
            critic_assessment: h.critic_assessment || undefined,
        })),
        reasoning_context: pythonOutput.reasoning_context,
        gap_analysis_used: pythonOutput.gap_analysis_used,
        reflection_rounds: pythonOutput.reflection_rounds,
        generation_strategy: generationStrategy,
        engine_used: pythonOutput.engine_used,
    };

    const critic_output: CriticOutput = {
        assessments: normalizedHypotheses
            .filter(h => h.critic_assessment)
            .map(h => h.critic_assessment!),
        overall_recommendation: '',
    };

    return { brainstormer_output, hypothesis_pipeline_output, critic_output };
}

function mapHypothesisType(pyType: string): 'scale' | 'modality_shift' | 'architecture_ablation' {
    const mapping: Record<string, 'scale' | 'modality_shift' | 'architecture_ablation'> = {
        scale: 'scale',
        modality_shift: 'modality_shift',
        architecture_ablation: 'architecture_ablation',
        cross_domain_transfer: 'modality_shift',
        efficiency_optimization: 'scale',
        failure_mode_analysis: 'architecture_ablation',
        data_augmentation: 'scale',
        theoretical_extension: 'architecture_ablation',
        combination: 'modality_shift',
        constraint_relaxation: 'modality_shift',
    };
    return mapping[pyType] || 'scale';
}

function extractArxivId(text: string | null | undefined): string | null {
    if (!text) return null;

    const cleaned = text.trim();
    const candidates = [
        cleaned,
        cleaned.replace(/\.pdf$/i, ''),
        cleaned.split('/').pop() || '',
        cleaned.split('_').pop() || '',
    ];

    for (const candidate of candidates) {
        const value = candidate.trim();
        if (value && isArxivId(value)) {
            return normalizeArxivId(value);
        }
    }

    const regexMatch = cleaned.match(/(\d{4}\.\d{4,5}(?:v\d+)?)/i);
    if (regexMatch?.[1] && isArxivId(regexMatch[1])) {
        return normalizeArxivId(regexMatch[1]);
    }

    return null;
}

async function resolveArxivIdForSession(
    state: StrategistRoomState,
    supabase: Awaited<ReturnType<typeof createServerSupabaseClient>>
): Promise<string | null> {
    const inState = extractArxivId(state.arxiv_id || null);
    if (inState) return inState;

    if (!state.document_id) return null;

    const { data: doc, error } = await supabase
        .from('documents')
        .select('filename, storage_path')
        .eq('id', state.document_id)
        .single();

    if (error || !doc) {
        return null;
    }

    const fromFilename = extractArxivId((doc as { filename?: string | null }).filename || null);
    if (fromFilename) {
        logger.info('Recovered arXiv ID from document filename', {
            document_id: state.document_id,
            arxivId: fromFilename,
        });
        return fromFilename;
    }

    const fromStoragePath = extractArxivId((doc as { storage_path?: string | null }).storage_path || null);
    if (fromStoragePath) {
        logger.info('Recovered arXiv ID from document storage path', {
            document_id: state.document_id,
            arxivId: fromStoragePath,
        });
        return fromStoragePath;
    }

    return null;
}

async function resolveDocumentStorageForSession(
    state: StrategistRoomState,
    supabase: Awaited<ReturnType<typeof createServerSupabaseClient>>
): Promise<{ filename: string; storagePath: string } | null> {
    if (!state.document_id) return null;

    const { data: doc, error } = await supabase
        .from('documents')
        .select('filename, storage_path')
        .eq('id', state.document_id)
        .single();

    if (error || !doc) {
        logger.warn('Failed to resolve document storage metadata', {
            document_id: state.document_id,
            error: error?.message || 'no_data',
        });
        return null;
    }

    const filename = String((doc as { filename?: string | null }).filename || 'uploaded.pdf');
    const storagePath = String((doc as { storage_path?: string | null }).storage_path || '');
    if (!storagePath) {
        return null;
    }

    return { filename, storagePath };
}

function sanitizeFileStem(name: string): string {
    const raw = name.replace(/\.pdf$/i, '');
    const clean = raw.replace(/[^a-zA-Z0-9._-]+/g, '_').replace(/^_+|_+$/g, '');
    return clean || 'uploaded';
}

async function downloadStoredPdfToTemp(
    storagePath: string,
    filename: string,
    userId: string,
    documentId: string
): Promise<string> {
    const adminSupabase = createAdminSupabaseClient();
    const { data, error } = await adminSupabase.storage.from(config.supabase.paperBucket).download(storagePath);
    if (error || !data) {
        throw new Error(`Failed to download uploaded PDF from storage: ${error?.message || 'no_data'}`);
    }

    const arrayBuffer = await data.arrayBuffer();
    const pdfBuffer = Buffer.from(arrayBuffer);
    if (pdfBuffer.length === 0) {
        throw new Error('Stored PDF is empty');
    }

    const stem = sanitizeFileStem(filename);
    const tempPath = path.join(
        os.tmpdir(),
        `vreda_hyp_${userId}_${documentId}_${Date.now()}_${stem}.pdf`
    );
    await fs.writeFile(tempPath, pdfBuffer);

    logger.info('Prepared uploaded PDF for hypothesis service', {
        documentId,
        storagePath,
        tempPath,
        sizeBytes: pdfBuffer.length,
    });

    return tempPath;
}

// ─── Main Route Handler ─────────────────────────────────

/**
 * POST /api/strategist/hypothesize
 *
 * Calls the Python hypothesis-room service for advanced 8-stage pipeline.
 * The Python service (services/hypothesis-room) MUST be running.
 *
 * Body: { session_id: string, message: string }
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { session_id, message } = body;
        const requestedEngineRaw = typeof body.hypothesis_engine === 'string' ? body.hypothesis_engine.toLowerCase() : '';
        const requestedEngine: HypothesisEngine = requestedEngineRaw === 'claude' ? 'claude' : 'gpt';

        try {
            validateUUID(session_id, 'session_id');
            validateMessage(message);
        } catch (error) {
            if (error instanceof ValidationError) {
                return NextResponse.json({ error: error.message }, { status: 400 });
            }
            throw error;
        }

        // Load session state
        const { data: session, error: sessionError } = await supabase
            .from('strategist_sessions')
            .select('*')
            .eq('id', session_id)
            .single();

        if (sessionError || !session) {
            return NextResponse.json(
                { error: `Session not found: ${sessionError?.message || 'no data'}` },
                { status: 404 }
            );
        }

        const state = session.state as StrategistRoomState;
        state.hypothesis_engine_preference = requestedEngine;

        void appendQuestEvent(supabase, {
            conversation_id: state.conversation_id,
            document_id: state.document_id,
            session_id,
            user_id: user.id,
            room: 'hypothesis',
            event_key: 'hypothesize_started',
            level: 'info',
            status: 'active',
            message: 'Hypothesis generation started.',
            metadata: { source: 'api/strategist/hypothesize' },
        });

        // Defensive: ensure state fields exist
        if (!state.user_refinement_history) state.user_refinement_history = [];
        if (!state.errors) state.errors = [];

        const recoveredArxivId = await resolveArxivIdForSession(state, supabase);
        if (recoveredArxivId) {
            state.arxiv_id = recoveredArxivId;
        }

        // Recovery: if paper_analysis is missing, re-run initial analysis
        if (!state.paper_analysis) {
            const { data: orderedChunks } = await supabase
                .from('document_chunks')
                .select('content')
                .eq('document_id', state.document_id)
                .order('chunk_index', { ascending: true })
                .limit(25);
            const recoveryContext = orderedChunks?.map((c: { content: string }) => c.content).join('\n\n---\n\n') || '';

            if (!recoveryContext.trim()) {
                return NextResponse.json(
                    { error: 'No paper content found. Please re-upload or re-fetch the paper.' },
                    { status: 400 }
                );
            }

            logger.info('Hypothesize: paper_analysis missing, re-running initial analysis', {
                session_id,
                document_id: state.document_id,
            });

            try {
                const recoveredState = await runInitialAnalysis(
                    recoveryContext, state.document_id, state.conversation_id, user.id, state.arxiv_id || null
                );
                state.paper_analysis = recoveredState.paper_analysis;
                state.code_path = recoveredState.code_path;
                state.research_intelligence = recoveredState.research_intelligence;
                if (!state.arxiv_id && recoveredState.arxiv_id) {
                    state.arxiv_id = recoveredState.arxiv_id;
                }

                if (!state.paper_analysis) {
                    const errDetails = recoveredState.errors?.length
                        ? recoveredState.errors.map((e: { message: string }) => e.message).join('; ')
                        : 'Unknown reason';
                    return NextResponse.json({ error: `Paper analysis failed: ${errDetails}` }, { status: 500 });
                }

                await supabase
                    .from('strategist_sessions')
                    .update({ state, phase: 'analysis_complete', updated_at: new Date().toISOString() })
                    .eq('id', session_id);
            } catch (err) {
                const errMsg = err instanceof Error ? err.message : String(err);
                logger.error('Hypothesize: recovery analysis failed', new Error(errMsg));
                return NextResponse.json({ error: `Paper analysis failed: ${errMsg}` }, { status: 500 });
            }
        }

        // Track user message
        state.phase = 'brainstorming';
        state.user_refinement_history.push({
            message,
            timestamp: new Date().toISOString(),
        });
        const requestedHypothesisCount = inferRequestedHypothesisCount(message);

        const selectedServiceUrl =
            requestedEngine === 'claude'
                ? config.hypothesisClaudeService.url
                : config.hypothesisGptService.url;
        const serviceStatus = await ensureHypothesisServiceReady(selectedServiceUrl, requestedEngine);
        if (!serviceStatus.ready) {
            const engineLabel = requestedEngine.toUpperCase();
            logger.error(`${engineLabel} hypothesis service is not ready`, new Error(serviceStatus.detail || 'Service unavailable'));
            void appendQuestEvent(supabase, {
                conversation_id: state.conversation_id,
                document_id: state.document_id,
                session_id,
                user_id: user.id,
                room: 'hypothesis',
                event_key: 'hypothesize_service_unavailable',
                level: 'error',
                status: 'error',
                message: serviceStatus.detail || `${engineLabel} hypothesis service is not running.`,
            });
            const startCommand =
                requestedEngine === 'claude'
                    ? 'cd services/hypothesis-room && source .venv/bin/activate && python -m hypo_claude.server'
                    : 'cd services/hypothesis-room/hypo-gpt && PYTHONPATH=src:.. python -m hypo_gpt.server';
            return NextResponse.json(
                {
                    error: `${serviceStatus.detail || `${engineLabel} hypothesis service is not running.`} Start it with: ${startCommand}`,
                },
                { status: 503 }
            );
        }

        // ─── Call Python Service ───
        try {
            const arxivId = await resolveArxivIdForSession(state, supabase);
            const domain = state.paper_analysis?.domain || 'other';
            let tempPdfPath: string | null = null;
            let serviceInput: HypothesisServiceInput | null = null;

            if (arxivId) {
                state.arxiv_id = arxivId;
                serviceInput = { arxivId };
            } else {
                const storageMeta = await resolveDocumentStorageForSession(state, supabase);
                if (!storageMeta || !state.document_id) {
                    return NextResponse.json(
                        { error: 'No valid document source found for hypothesis generation. Please re-upload the PDF.' },
                        { status: 400 }
                    );
                }
                try {
                    tempPdfPath = await downloadStoredPdfToTemp(
                        storageMeta.storagePath,
                        storageMeta.filename,
                        user.id,
                        state.document_id
                    );
                } catch (downloadError) {
                    const detail = downloadError instanceof Error ? downloadError.message : String(downloadError);
                    logger.error('Failed preparing uploaded PDF for hypothesis service', new Error(detail), {
                        document_id: state.document_id,
                        storagePath: storageMeta.storagePath,
                    });
                    return NextResponse.json(
                        { error: `Could not prepare uploaded PDF for hypothesis generation: ${detail}` },
                        { status: 500 }
                    );
                }
                serviceInput = { pdfPath: tempPdfPath };
            }
            logger.info('Using hypothesis service', {
                arxivId: serviceInput.arxivId || null,
                usesUploadedPdf: Boolean(serviceInput.pdfPath),
                domain,
                requestedHypothesisCount,
                engine: requestedEngine,
                session_id,
            });

            try {
                const pythonOutput = await callHypothesisService(serviceInput, domain, selectedServiceUrl, requestedEngine, {
                    topK: requestedHypothesisCount ?? undefined,
                });
                const { brainstormer_output, hypothesis_pipeline_output, critic_output } = mapPythonToFrontend(pythonOutput);
                const generatedCount = hypothesis_pipeline_output.hypotheses.length;
                if (generatedCount === 0) {
                    throw new Error(
                        'Pipeline completed but returned zero hypotheses. Check hypothesis-room grounding and refinement providers.'
                    );
                }

                state.brainstormer_output = brainstormer_output;
                state.hypothesis_pipeline_output = hypothesis_pipeline_output;
                state.critic_output = critic_output;
                state.last_hypothesis_engine_used = pythonOutput.engine_used || requestedEngine;
                state.phase = 'hypothesis_presented';
                state.updated_at = new Date().toISOString();

                logger.info('Python hypothesis service complete', {
                    session_id,
                    hypothesesCount: generatedCount,
                    engine: pythonOutput.engine_used || requestedEngine,
                    strategy: pythonOutput.generation_strategy,
                    hasPortfolioAudit: !!pythonOutput.portfolio_audit,
                    eloRatings: hypothesis_pipeline_output.hypotheses.map(h => ({ id: h.id, elo: h.composite_score })),
                });

                void appendQuestEvent(supabase, {
                    conversation_id: state.conversation_id,
                    document_id: state.document_id,
                    session_id,
                    user_id: user.id,
                    room: 'hypothesis',
                    event_key: 'hypothesize_completed',
                    level: 'success',
                    status: 'done',
                    message: `Hypothesis pipeline completed with ${generatedCount} options.`,
                    metadata: {
                        strategy: pythonOutput.generation_strategy,
                        source: 'python',
                        engine: pythonOutput.engine_used || requestedEngine,
                    },
                });
            } finally {
                if (tempPdfPath) {
                    await fs.unlink(tempPdfPath).catch((cleanupError) => {
                        logger.warn('Failed to remove temporary PDF after hypothesis generation', {
                            tempPdfPath,
                            error: cleanupError instanceof Error ? cleanupError.message : String(cleanupError),
                        });
                    });
                }
            }

        } catch (serviceError) {
            const errMsg = serviceError instanceof Error ? serviceError.message : String(serviceError);
            logger.error('Python hypothesis service failed', new Error(errMsg));
            void appendQuestEvent(supabase, {
                conversation_id: state.conversation_id,
                document_id: state.document_id,
                session_id,
                user_id: user.id,
                room: 'hypothesis',
                event_key: 'hypothesize_failed',
                level: 'error',
                status: 'error',
                message: `Hypothesis generation failed: ${errMsg}`,
            });
            return NextResponse.json({ error: `Hypothesis generation failed: ${errMsg}` }, { status: 500 });
        }

        // ─── Save & Respond ───
        await supabase
            .from('strategist_sessions')
            .update({ state, phase: state.phase, updated_at: new Date().toISOString() })
            .eq('id', session_id);

        if (state.brainstormer_output && state.brainstormer_output.hypotheses.length > 0) {
            const hypCount = state.brainstormer_output.hypotheses.length;
            await supabase.from('messages').insert({
                conversation_id: state.conversation_id,
                role: 'assistant',
                content: `## Hypothesis Proposals\n\nI've generated ${hypCount} forward hypotheses using the advanced 8-stage pipeline (ResearchFrame extraction, iterative gap synthesis, archetype-mapped seeds, Elo tournament ranking, portfolio audit). Select one to estimate the execution budget.`,
                metadata: {
                    type: 'hypothesis_options',
                    document_id: state.document_id,
                    session_id,
                    hypothesis_engine: state.hypothesis_engine_preference || requestedEngine,
                    engine_used: state.last_hypothesis_engine_used || requestedEngine,
                    brainstormer_output: state.brainstormer_output,
                    hypothesis_pipeline_output: state.hypothesis_pipeline_output,
                },
            });
        } else {
            await supabase.from('messages').insert({
                conversation_id: state.conversation_id,
                role: 'assistant',
                content: '## Hypothesis Generation Warning\n\nThe pipeline completed without usable hypotheses. Please retry after provider limits reset.',
                metadata: {
                    type: 'hypothesis_warning',
                    document_id: state.document_id,
                    session_id,
                },
            });
        }

        return NextResponse.json({
            session_id,
            phase: state.phase,
            brainstormer_output: state.brainstormer_output,
            hypothesis_pipeline_output: state.hypothesis_pipeline_output,
            state,
        });
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        logger.error('Strategist hypothesize error', error instanceof Error ? error : new Error(errorMessage));
        return NextResponse.json({ error: errorMessage }, { status: 500 });
    }
}
