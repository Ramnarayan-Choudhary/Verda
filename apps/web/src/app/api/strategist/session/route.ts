import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';

/**
 * GET /api/strategist/session?conversation_id=<uuid>
 * Lookup the most recent strategist session for a conversation.
 * Returns session_id and phase, or null if no session exists.
 */
export async function GET(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const conversationId = request.nextUrl.searchParams.get('conversation_id');

        if (!conversationId) {
            return NextResponse.json({ error: 'conversation_id is required' }, { status: 400 });
        }

        try {
            validateUUID(conversationId, 'conversation_id');
        } catch (error) {
            if (error instanceof ValidationError) {
                return NextResponse.json({ error: error.message }, { status: 400 });
            }
            throw error;
        }

        const { data: session, error: sessionError } = await supabase
            .from('strategist_sessions')
            .select('id, phase')
            .eq('conversation_id', conversationId)
            .eq('user_id', user.id)
            .order('updated_at', { ascending: false })
            .limit(1)
            .single();

        if (sessionError || !session) {
            // No session found — that's fine, return idle state
            return NextResponse.json({
                session_id: null,
                phase: 'idle',
            });
        }

        return NextResponse.json({
            session_id: session.id,
            phase: session.phase,
        });
    } catch (error) {
        logger.error('Strategist session lookup error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
