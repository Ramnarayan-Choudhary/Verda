import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { runInitialAnalysis } from '@/lib/agents/strategist-room';
import { retrieveRelevantChunks } from '@/lib/agents/strategist';
import { validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';

export const maxDuration = 60;

/**
 * POST /api/strategist/analyze
 * Re-run initial analysis (Parser + Scout) for a document.
 * Used when initial analysis failed and user wants to retry.
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { document_id, conversation_id } = body;

        try {
            validateUUID(document_id, 'document_id');
            validateUUID(conversation_id, 'conversation_id');
        } catch (error) {
            if (error instanceof ValidationError) {
                return NextResponse.json({ error: error.message }, { status: 400 });
            }
            throw error;
        }

        // Retrieve paper context via RAG chunks
        const chunks = await retrieveRelevantChunks(
            document_id,
            'hypothesis variables methodology results conclusions experiment design architecture model training',
            supabase,
            15
        );

        const paperContext = chunks.map(c => c.content).join('\n\n---\n\n');

        if (!paperContext.trim()) {
            return NextResponse.json(
                { error: 'No paper content available for analysis.' },
                { status: 422 }
            );
        }

        // Run initial analysis (Parser + Scout)
        const state = await runInitialAnalysis(paperContext, document_id, conversation_id, user.id);

        // Store session in database
        const { error: sessionError } = await supabase
            .from('strategist_sessions')
            .upsert({
                id: state.session_id,
                document_id,
                conversation_id,
                user_id: user.id,
                state,
                phase: state.phase,
                updated_at: new Date().toISOString(),
            });

        if (sessionError) {
            logger.error('Failed to store strategist session', new Error(sessionError.message), {
                sessionId: state.session_id,
                documentId: document_id,
            });
        }

        // Store analysis message
        await supabase.from('messages').insert({
            conversation_id,
            role: 'assistant',
            content: state.paper_analysis
                ? `## Paper Analysis Complete\n\nI've analyzed **"${state.paper_analysis.title}"** and assessed code availability.`
                : '## Analysis Error\n\nFailed to analyze the paper. Please try again.',
            metadata: {
                type: 'paper_analysis',
                document_id,
                session_id: state.session_id,
                paper_analysis: state.paper_analysis,
                code_path: state.code_path,
            },
        });

        return NextResponse.json({
            session_id: state.session_id,
            phase: state.phase,
            state,
        });
    } catch (error) {
        logger.error('Strategist analyze error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
