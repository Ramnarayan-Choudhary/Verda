// ============================================
// VREDA.ai Type Definitions
// ============================================

export * from './strategist';
export * from './research-intelligence';
export * from './quest';

import type {
    PaperAnalysis,
    CodePathAssessment,
    BrainstormerOutput,
    BudgetQuote,
    EnhancedResearchManifest,
    GeneratorOutput,
} from './strategist';
import type { QuestDomain } from './quest';

export interface Conversation {
    id: string;
    user_id: string;
    title: string;
    domain?: QuestDomain;
    created_at: string;
}

export interface Message {
    id: string;
    conversation_id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    metadata: MessageMetadata;
    created_at: string;
}

export type PipelineStep =
    | 'metadata'
    | 'download'
    | 'upload_storage'
    | 'extract_text'
    | 'chunking'
    | 'embedding'
    | 'storing_chunks'
    | 'research_intelligence'
    | 'strategist';

export interface PipelineProgressEvent {
    type: 'progress' | 'warning' | 'complete' | 'error';
    step?: PipelineStep;
    message: string;
    current?: number;
    total?: number;
    data?: Record<string, unknown>;
}

export interface MessageMetadata {
    type?:
        | 'text'
        | 'pdf_upload'
        | 'research_manifest'
        | 'error'
        | 'paper_analysis'
        | 'hypothesis_options'
        | 'budget_quote'
        | 'enhanced_manifest'
        | 'literature_search'
        | 'pipeline_progress';
    document_id?: string;
    filename?: string;
    search_results?: import('@/lib/literature/types').PaperMetadata[];
    search_query?: string;
    manifest?: ResearchManifest;
    session_id?: string;
    paper_analysis?: PaperAnalysis;
    code_path?: CodePathAssessment;
    brainstormer_output?: BrainstormerOutput;
    hypothesis_pipeline_output?: GeneratorOutput;
    hypothesis_engine?: 'gpt' | 'claude';
    engine_used?: 'gpt' | 'claude' | 'legacy';
    budget_quote?: BudgetQuote;
    enhanced_manifest?: EnhancedResearchManifest;
    pipeline_events?: PipelineProgressEvent[];
    pipeline_title?: string;
    research_intelligence?: import('./research-intelligence').ResearchIntelligence;
}

export interface Document {
    id: string;
    user_id: string;
    conversation_id: string;
    filename: string;
    storage_path: string;
    status: 'processing' | 'ready' | 'error';
    created_at: string;
}

export interface DocumentChunk {
    id: string;
    document_id: string;
    content: string;
    embedding: number[];
    chunk_index: number;
    created_at: string;
}

export interface ResearchManifest {
    hypothesis: string;
    variables: {
        independent: string[];
        dependent: string[];
        controlled: string[];
    };
    libraries: string[];
    budget_estimate: {
        tokens_used: number;
        estimated_cost_usd: number;
    };
    execution_steps: string[];
    anti_gravity_check: {
        passed: boolean;
        violations: string[];
    };
}

export interface ChunkMatch {
    id: string;
    content: string;
    similarity: number;
}
