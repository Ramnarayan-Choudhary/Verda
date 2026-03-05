import { NextRequest, NextResponse } from 'next/server';
import { runChatQuery } from '@/lib/agents/strategist';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { createAdminSupabaseClient } from '@/lib/supabase/admin';
import { validateMessage, validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';

export async function POST(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();

        const {
            data: { user },
            error: authError,
        } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { message, conversation_id } = await request.json();

        try {
            validateMessage(message);
            validateUUID(conversation_id, 'conversation_id');
        } catch (error) {
            if (error instanceof ValidationError) {
                return NextResponse.json({ error: error.message }, { status: 400 });
            }
            throw error;
        }

        // Save user message
        const { error: msgError } = await supabase.from('messages').insert({
            conversation_id,
            role: 'user',
            content: message,
            metadata: { type: 'text' },
        });

        if (msgError) {
            logger.error('Failed to save user message', new Error(msgError.message), { conversation_id });
        }

        // Get document for this conversation (if any).
        // Accept any non-error status — chunks are available for RAG even while
        // strategist analysis is still running (status may be 'processing:*').
        const { data: docs } = await supabase
            .from('documents')
            .select('id, status')
            .eq('conversation_id', conversation_id)
            .not('status', 'like', 'error%')
            .order('created_at', { ascending: false })
            .limit(1);

        const documentId = docs?.[0]?.id || null;

        // Get paper analysis from strategist session (if available)
        let paperAnalysis = null;
        if (documentId) {
            const { data: sessions } = await supabase
                .from('strategist_sessions')
                .select('state')
                .eq('conversation_id', conversation_id)
                .order('created_at', { ascending: false })
                .limit(1);

            const state = sessions?.[0]?.state;
            if (state?.paper_analysis) {
                paperAnalysis = state.paper_analysis;
            }
        }

        // Get conversation history (last 10 messages for context)
        const { data: history } = await supabase
            .from('messages')
            .select('role, content')
            .eq('conversation_id', conversation_id)
            .order('created_at', { ascending: true })
            .limit(10);

        const conversationHistory = (history || [])
            .filter(m => m.role !== 'system')
            .map(m => ({ role: m.role, content: m.content }));

        const stream = await runChatQuery(
            documentId,
            message,
            conversationHistory.slice(0, -1),
            paperAnalysis
        );

        // Tee stream: one for response, one for background save
        const [streamForResponse, streamForSave] = stream.tee();

        // Background save using admin client (doesn't depend on user cookies)
        (async () => {
            try {
                const reader = streamForSave.getReader();
                const decoder = new TextDecoder();
                let fullResponse = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    fullResponse += decoder.decode(value, { stream: true });
                }

                if (fullResponse) {
                    const adminSupabase = createAdminSupabaseClient();
                    await adminSupabase.from('messages').insert({
                        conversation_id,
                        role: 'assistant',
                        content: fullResponse,
                        metadata: { type: 'text' },
                    });
                }
            } catch (err) {
                logger.error('Failed to save assistant response', err instanceof Error ? err : new Error(String(err)), {
                    conversation_id,
                });
            }
        })();

        return new Response(streamForResponse, {
            headers: {
                'Content-Type': 'text/plain; charset=utf-8',
                'Cache-Control': 'no-cache',
            },
        });
    } catch (error) {
        logger.error('Chat API error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
