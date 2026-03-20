import type { StrategistRoomState } from '@/types/strategist';

/**
 * Creates the initial state for a Strategist Room session.
 * Called when a PDF is uploaded and initial analysis begins.
 */
export function createInitialState(
    documentId: string,
    conversationId: string,
    userId: string
): StrategistRoomState {
    return {
        session_id: crypto.randomUUID(),
        document_id: documentId,
        conversation_id: conversationId,
        user_id: userId,
        hypothesis_engine_preference: 'claude',
        last_hypothesis_engine_used: null,

        phase: 'idle',

        paper_analysis: null,
        research_intelligence: null,
        code_path: null,

        brainstormer_output: null,
        critic_output: null,
        hypothesis_pipeline_output: null,
        user_refinement_history: [],
        selected_hypothesis_id: null,

        budget_quote: null,

        risk_assessment: null,
        approved: false,

        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        errors: [],
    };
}
