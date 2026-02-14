import { embedText } from '@/lib/embeddings/gemini';
import { STRATEGIST_SYSTEM_PROMPT, STRATEGIST_USER_PROMPT } from './prompts';
import type { ResearchManifest, ChunkMatch } from '@/types';
import { SupabaseClient } from '@supabase/supabase-js';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { openRouter } from '@/lib/openrouter';
import { k2think } from '@/lib/k2think';
import { config } from '@/lib/config';
import { logger } from '@/lib/logger';
import { LLMError } from '@/lib/errors';

/**
 * Retrieve relevant chunks from Supabase pgvector using similarity search.
 * Returns empty array if embedding or search fails (non-fatal for chat).
 */
export async function retrieveRelevantChunks(
    documentId: string,
    query: string,
    supabase: SupabaseClient,
    matchCount: number = 10
): Promise<ChunkMatch[]> {
    try {
        const queryEmbedding = await embedText(query);

        const { data, error } = await supabase.rpc('match_chunks', {
            query_embedding: queryEmbedding,
            match_count: matchCount,
            filter_doc_id: documentId,
        });

        if (error) {
            logger.error('Similarity search failed', new Error(error.message), { documentId });
            return [];
        }

        return data || [];
    } catch (error) {
        logger.error('RAG retrieval failed', error instanceof Error ? error : new Error(String(error)), { documentId });
        return [];
    }
}

/**
 * Run the Strategist Agent on a document.
 * 1. Retrieves relevant chunks via similarity search
 * 2. Sends to OpenRouter for analysis
 * 3. Parses and returns Research Manifest
 */
export async function runStrategistAgent(
    documentId: string,
    supabase?: SupabaseClient
): Promise<ResearchManifest> {
    const client = supabase || (await createServerSupabaseClient());

    const chunks = await retrieveRelevantChunks(
        documentId,
        'hypothesis variables methodology results conclusions experiment design',
        client,
        15
    );

    const paperContext = chunks.map(c => c.content).join('\n\n---\n\n');

    if (!paperContext.trim()) {
        throw new LLMError('No context available for Strategist Agent — cannot analyze without paper content', {
            documentId,
        });
    }

    logger.info('Running Strategist Agent', { documentId, contextChunks: chunks.length });

    const messages: { role: 'system' | 'user'; content: string }[] = [
        { role: 'system', content: STRATEGIST_SYSTEM_PROMPT },
        { role: 'user', content: STRATEGIST_USER_PROMPT(paperContext) },
    ];

    const parseManifest = (responseText: string): ResearchManifest => {
        try {
            return JSON.parse(responseText) as ResearchManifest;
        } catch {
            const jsonMatch = responseText.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return JSON.parse(jsonMatch[0]) as ResearchManifest;
            }
            throw new LLMError('Failed to parse Research Manifest from AI response', {
                documentId,
                responsePreview: responseText.substring(0, 200),
            });
        }
    };

    // Try OpenRouter first
    try {
        const completion = await openRouter.chat.completions.create({
            model: config.openrouter.model,
            messages,
            temperature: 0.2,
            response_format: { type: 'json_object' },
        });
        const responseText = completion.choices[0].message.content || '{}';
        const manifest = parseManifest(responseText);
        logger.info('Strategist Agent complete (OpenRouter)', { documentId, hypothesis: manifest.hypothesis?.substring(0, 80) });
        return manifest;
    } catch (primaryError) {
        if (k2think) {
            logger.warn('Strategist Agent: OpenRouter failed, falling back to K2 Think', {
                documentId,
                error: primaryError instanceof Error ? primaryError.message : String(primaryError),
            });
            try {
                const completion = await k2think.chat.completions.create({
                    model: config.k2think.model,
                    messages,
                    temperature: 0.2,
                    response_format: { type: 'json_object' },
                });
                const responseText = completion.choices[0].message.content || '{}';
                const manifest = parseManifest(responseText);
                logger.info('Strategist Agent complete (K2 Think fallback)', { documentId, hypothesis: manifest.hypothesis?.substring(0, 80) });
                return manifest;
            } catch (fallbackError) {
                logger.error('Strategist Agent: K2 Think fallback also failed', fallbackError instanceof Error ? fallbackError : new Error(String(fallbackError)));
            }
        }
        throw primaryError;
    }
}

/**
 * Run a RAG-powered chat query against document context.
 * Returns a ReadableStream for streaming responses.
 */
export async function runChatQuery(
    documentId: string | null,
    userMessage: string,
    conversationHistory: { role: string; content: string }[]
): Promise<ReadableStream> {
    let context = 'No papers uploaded yet. Respond helpfully using general scientific knowledge.';

    if (documentId) {
        const supabase = await createServerSupabaseClient();
        const chunks = await retrieveRelevantChunks(documentId, userMessage, supabase, 5);
        if (chunks.length > 0) {
            context = chunks.map(c => c.content).join('\n\n---\n\n');
        }
    }

    const systemPrompt = `You are VREDA.ai — a Scientific Research Assistant.

## RULES
1. Base your answers on the provided paper context when available.
2. If the user asks about something not in the paper, clearly state you are providing general knowledge.
3. Be precise and scientific in your language.
4. Format responses with clear structure using markdown.

## PAPER CONTEXT
${context}`;

    const messages = [
        { role: 'system' as const, content: systemPrompt },
        ...conversationHistory.map(msg => ({
            role: msg.role as 'user' | 'assistant' | 'system',
            content: msg.content,
        })),
        { role: 'user' as const, content: userMessage },
    ];

    const streamFromProvider = async (client: import('openai').default, model: string) => {
        return client.chat.completions.create({
            model,
            messages,
            temperature: 0.7,
            stream: true,
        });
    };

    // Try OpenRouter first, fall back to K2 Think
    let completionStream;
    try {
        completionStream = await streamFromProvider(openRouter, config.openrouter.model);
    } catch (primaryError) {
        if (k2think) {
            logger.warn('Chat query: OpenRouter failed, falling back to K2 Think', {
                error: primaryError instanceof Error ? primaryError.message : String(primaryError),
            });
            completionStream = await streamFromProvider(k2think, config.k2think.model);
        } else {
            throw primaryError;
        }
    }

    return new ReadableStream({
        async start(controller) {
            try {
                for await (const chunk of completionStream) {
                    const text = chunk.choices[0]?.delta?.content || '';
                    if (text) {
                        controller.enqueue(new TextEncoder().encode(text));
                    }
                }
                controller.close();
            } catch (error) {
                logger.error('Chat stream error', error instanceof Error ? error : new Error(String(error)));
                controller.error(error);
            }
        },
    });
}
