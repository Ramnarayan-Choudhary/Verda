import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { finalizeManifest } from '@/lib/agents/strategist-room';
import { validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';
import type { StrategistRoomState } from '@/types/strategist';

export const maxDuration = 30;

/**
 * POST /api/strategist/approve
 * Finalize the Enhanced Research Manifest.
 * Body: { session_id: string }
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { session_id } = body;

        try {
            validateUUID(session_id, 'session_id');
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

        // Finalize manifest
        const manifest = finalizeManifest(state);

        // Update session in DB
        await supabase
            .from('strategist_sessions')
            .update({
                state: { ...state, approved: true, phase: 'approved', updated_at: new Date().toISOString() },
                phase: 'approved',
                updated_at: new Date().toISOString(),
            })
            .eq('id', session_id);

        // Store enhanced manifest message
        await supabase.from('messages').insert({
            conversation_id: state.conversation_id,
            role: 'assistant',
            content: `## Research Manifest Approved\n\nYour Enhanced Research Manifest is ready. The Coder Room can now execute the experiment based on the hypothesis: **"${manifest.hypothesis.title}"**`,
            metadata: {
                type: 'enhanced_manifest',
                document_id: state.document_id,
                session_id,
                enhanced_manifest: manifest,
            },
        });

        return NextResponse.json({
            session_id,
            phase: 'approved',
            manifest,
        });
    } catch (error) {
        logger.error('Strategist approve error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
