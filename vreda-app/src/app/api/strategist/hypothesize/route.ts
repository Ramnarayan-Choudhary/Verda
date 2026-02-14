import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { runHypothesisGeneration } from '@/lib/agents/strategist-room';
import { retrieveRelevantChunks } from '@/lib/agents/strategist';
import { validateUUID, validateMessage } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';
import type { StrategistRoomState } from '@/types/strategist';

export const maxDuration = 60;

/**
 * POST /api/strategist/hypothesize
 * Run or refine hypotheses for a strategist session.
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
            return NextResponse.json({ error: 'Session not found' }, { status: 404 });
        }

        const state = session.state as StrategistRoomState;

        // Retrieve paper context
        const chunks = await retrieveRelevantChunks(
            state.document_id,
            message,
            supabase,
            10
        );
        const paperContext = chunks.map(c => c.content).join('\n\n---\n\n');

        // Run brainstormer
        const updatedState = await runHypothesisGeneration(state, paperContext, message);

        // Update session in DB
        await supabase
            .from('strategist_sessions')
            .update({
                state: updatedState,
                phase: updatedState.phase,
                updated_at: new Date().toISOString(),
            })
            .eq('id', session_id);

        // Store hypothesis message
        if (updatedState.brainstormer_output) {
            await supabase.from('messages').insert({
                conversation_id: state.conversation_id,
                role: 'assistant',
                content: `## Hypothesis Proposals\n\nI've generated 3 forward hypotheses based on the paper analysis and your input. Select one to estimate the execution budget.`,
                metadata: {
                    type: 'hypothesis_options',
                    document_id: state.document_id,
                    session_id,
                    brainstormer_output: updatedState.brainstormer_output,
                },
            });
        }

        return NextResponse.json({
            session_id,
            phase: updatedState.phase,
            brainstormer_output: updatedState.brainstormer_output,
            state: updatedState,
        });
    } catch (error) {
        logger.error('Strategist hypothesize error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
