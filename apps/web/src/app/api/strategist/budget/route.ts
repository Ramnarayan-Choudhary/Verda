import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { runBudgetEstimation } from '@/lib/agents/strategist-room';
import { validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';
import type { StrategistRoomState } from '@/types/strategist';
import { appendQuestEvent } from '@/lib/quest-events';

export const maxDuration = 60;

/**
 * POST /api/strategist/budget
 * Calculate budget for a selected hypothesis.
 * Body: { session_id: string, hypothesis_id: string }
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { session_id, hypothesis_id } = body;

        try {
            validateUUID(session_id, 'session_id');
        } catch (error) {
            if (error instanceof ValidationError) {
                return NextResponse.json({ error: error.message }, { status: 400 });
            }
            throw error;
        }

        if (!hypothesis_id || typeof hypothesis_id !== 'string') {
            return NextResponse.json({ error: 'hypothesis_id is required' }, { status: 400 });
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

        void appendQuestEvent(supabase, {
            conversation_id: state.conversation_id,
            document_id: state.document_id,
            session_id,
            user_id: user.id,
            room: 'hypothesis',
            event_key: 'budget_started',
            level: 'info',
            status: 'active',
            message: `Budget estimation started for hypothesis ${hypothesis_id}.`,
        });

        // Run accountant
        const updatedState = await runBudgetEstimation(state, hypothesis_id);

        // Update session in DB
        await supabase
            .from('strategist_sessions')
            .update({
                state: updatedState,
                phase: updatedState.phase,
                updated_at: new Date().toISOString(),
            })
            .eq('id', session_id);

        // Store budget message
        if (updatedState.budget_quote) {
            const freeTierLabel = updatedState.budget_quote.free_tier_compatible
                ? 'Compatible with free tier!'
                : 'May require paid resources.';

            await supabase.from('messages').insert({
                conversation_id: state.conversation_id,
                role: 'assistant',
                content: `## Budget Estimate\n\nEstimated cost: **$${updatedState.budget_quote.summary.total_usd.toFixed(4)}** (${freeTierLabel})\n\nReview the breakdown below and approve to generate the execution manifest.`,
                metadata: {
                    type: 'budget_quote',
                    document_id: state.document_id,
                    session_id,
                    budget_quote: updatedState.budget_quote,
                },
            });

            void appendQuestEvent(supabase, {
                conversation_id: state.conversation_id,
                document_id: state.document_id,
                session_id,
                user_id: user.id,
                room: 'hypothesis',
                event_key: 'budget_completed',
                level: updatedState.budget_quote.free_tier_compatible ? 'success' : 'warn',
                status: 'done',
                message: `Budget estimated: $${updatedState.budget_quote.summary.total_usd.toFixed(4)}.`,
                metadata: {
                    hypothesis_id,
                    free_tier_compatible: updatedState.budget_quote.free_tier_compatible,
                },
            });
        }

        return NextResponse.json({
            session_id,
            phase: updatedState.phase,
            budget: updatedState.budget_quote,
            state: updatedState,
        });
    } catch (error) {
        logger.error('Strategist budget error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
