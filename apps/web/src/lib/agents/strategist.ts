import { embedText } from '@/lib/embeddings';
import type { ChunkMatch } from '@/types';
import { SupabaseClient } from '@supabase/supabase-js';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { openaiClient } from '@/lib/openai-client';
import { openRouter } from '@/lib/openrouter';
import { deepseek } from '@/lib/deepseek';
import { k2think } from '@/lib/k2think';
import { config } from '@/lib/config';
import { logger } from '@/lib/logger';
import type OpenAI from 'openai';

const CHAT_MAX_TOKENS = 2600;

type ProviderCandidate = { label: string; client: OpenAI; model: string };

function getProviderCandidates(): ProviderCandidate[] {
    const providers: ProviderCandidate[] = [];
    if (openaiClient) {
        providers.push({ label: 'OpenAI', client: openaiClient, model: config.openai.model });
    }
    if (deepseek) {
        providers.push({ label: 'DeepSeek', client: deepseek, model: config.deepseek.model });
    }
    if (openRouter) {
        providers.push({ label: 'OpenRouter', client: openRouter, model: config.openrouter.model });
    }
    if (k2think) {
        providers.push({ label: 'K2Think', client: k2think, model: config.k2think.model });
    }
    return providers;
}

function extractAffordableTokens(error: unknown): number | null {
    const message =
        error && typeof error === 'object' && 'message' in error
            ? String((error as { message?: unknown }).message || '')
            : String(error || '');
    const match = message.match(/can only afford\s+(\d+)/i);
    if (!match) return null;
    const parsed = Number(match[1]);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function buildFallbackChatResponse(
    userMessage: string,
    paperAnalysis?: { title: string; abstract_summary: string; key_claims: string[]; contributions: string[]; limitations: string[]; domain: string } | null,
    ragContext: string = ''
): string {
    const excerpts = ragContext
        .split('\n\n---\n\n')
        .map((chunk) => chunk.replace(/\s+/g, ' ').trim())
        .filter((chunk) => chunk.length > 40)
        .slice(0, 3);

    if (paperAnalysis) {
        const claims = paperAnalysis.key_claims.slice(0, 3).map((c) => `- ${c}`).join('\n');
        const contributions = paperAnalysis.contributions.slice(0, 3).map((c) => `- ${c}`).join('\n');
        const limits = paperAnalysis.limitations.slice(0, 2).map((c) => `- ${c}`).join('\n');

        return `## ${paperAnalysis.title}

### Quick Summary
${paperAnalysis.abstract_summary}

### Key Claims
${claims || '- Core claims were captured during paper parsing.'}

### Contributions
${contributions || '- Contributions are aligned with the reported claims.'}

### Limitations
${limits || '- Limitations were not explicitly extracted.'}

${excerpts.length > 0 ? `### Evidence Snippets\n${excerpts.map((e, i) => `${i + 1}. ${e.slice(0, 280)}...`).join('\n')}` : ''}

_Generated in resilient mode for: "${userMessage}"._`;
    }

    if (excerpts.length > 0) {
        return `## Paper Overview

I could not load the full paper analysis, but here are grounded snippets from the uploaded document:

${excerpts.map((e, i) => `${i + 1}. ${e.slice(0, 320)}...`).join('\n')}

If you want, I can still brainstorm hypotheses from this context.`;
    }

    return 'I could not retrieve paper context right now. Please retry after reprocessing the paper.';
}

function streamFromText(text: string): ReadableStream {
    return new ReadableStream({
        start(controller) {
            controller.enqueue(new TextEncoder().encode(text));
            controller.close();
        },
    });
}

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
 * Run a RAG-powered chat query against document context.
 * Returns a ReadableStream for streaming responses.
 *
 * When paperAnalysis is provided (from strategist session), it's included
 * in the system prompt so the LLM knows which paper is being discussed,
 * and the RAG query is augmented with the paper title for better retrieval.
 */
export async function runChatQuery(
    documentId: string | null,
    userMessage: string,
    conversationHistory: { role: string; content: string }[],
    paperAnalysis?: { title: string; abstract_summary: string; key_claims: string[]; contributions: string[]; limitations: string[]; domain: string } | null
): Promise<ReadableStream> {
    let ragContext = '';
    let paperOverview = '';

    if (documentId) {
        const supabase = await createServerSupabaseClient();

        // Augment vague queries with the paper title for better embedding retrieval.
        // Queries like "tell me about the paper" match bibliography chunks otherwise.
        let ragQuery = userMessage;
        if (paperAnalysis?.title) {
            const lowerMsg = userMessage.toLowerCase();
            const isVague = lowerMsg.includes('paper') || lowerMsg.includes('tell me') ||
                lowerMsg.includes('summary') || lowerMsg.includes('overview') ||
                lowerMsg.includes('what is') || lowerMsg.includes('about');
            if (isVague) {
                ragQuery = `${paperAnalysis.title}: ${userMessage}`;
            }
        }

        const chunks = await retrieveRelevantChunks(documentId, ragQuery, supabase, 8);
        if (chunks.length > 0) {
            ragContext = chunks.map(c => c.content).join('\n\n---\n\n');
        }
    }

    // Build paper overview from strategist analysis (if available)
    if (paperAnalysis) {
        paperOverview = `## PAPER OVERVIEW (from analysis)
**Title:** ${paperAnalysis.title}
**Domain:** ${paperAnalysis.domain}
**Abstract:** ${paperAnalysis.abstract_summary}
**Key Claims:** ${paperAnalysis.key_claims.join('; ')}
**Contributions:** ${paperAnalysis.contributions.join('; ')}
**Limitations:** ${paperAnalysis.limitations.join('; ')}`;
    }

    let contextSection: string;
    if (paperOverview && ragContext) {
        contextSection = `${paperOverview}\n\n## RELEVANT EXCERPTS FROM PAPER\n${ragContext}`;
    } else if (paperOverview) {
        contextSection = paperOverview;
    } else if (ragContext) {
        contextSection = `## PAPER CONTEXT\n${ragContext}`;
    } else {
        contextSection = 'No papers uploaded yet. Respond helpfully using general scientific knowledge.';
    }

    const systemPrompt = `You are VREDA.ai — a Scientific Research Assistant.

## RULES
1. When the user says "the paper" or "this paper", they mean the paper described in the PAPER OVERVIEW below.
2. Base your answers on the provided paper context and excerpts.
3. If the user asks about something not in the paper, clearly state you are providing general knowledge.
4. Be precise and scientific in your language.
5. Format responses with clear structure using markdown.

${contextSection}`;

    const messages = [
        { role: 'system' as const, content: systemPrompt },
        ...conversationHistory.map(msg => ({
            role: msg.role as 'user' | 'assistant' | 'system',
            content: msg.content,
        })),
        { role: 'user' as const, content: userMessage },
    ];

    const streamFromProvider = async (client: import('openai').default, model: string) => {
        const create = (tokenLimit: number) =>
            client.chat.completions.create({
                model,
                messages,
                temperature: 0.7,
                max_tokens: tokenLimit,
                stream: true,
            });

        try {
            return await create(CHAT_MAX_TOKENS);
        } catch (error) {
            const affordable = extractAffordableTokens(error);
            if (affordable && affordable < CHAT_MAX_TOKENS) {
                return create(Math.max(900, affordable - 120));
            }
            throw error;
        }
    };

    // Try providers in order: DeepSeek -> OpenRouter -> K2Think
    const providers = getProviderCandidates();
    let completionStream: Awaited<ReturnType<typeof streamFromProvider>> | null = null;
    for (const provider of providers) {
        try {
            completionStream = await streamFromProvider(provider.client, provider.model);
            break;
        } catch (error) {
            logger.warn(`Chat query: ${provider.label} failed`, {
                error: error instanceof Error ? error.message : String(error),
            });
        }
    }

    if (!completionStream) {
        const fallbackText = buildFallbackChatResponse(userMessage, paperAnalysis, ragContext);
        return streamFromText(fallbackText);
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
