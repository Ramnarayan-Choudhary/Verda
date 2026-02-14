import { openRouter } from '@/lib/openrouter';
import { k2think } from '@/lib/k2think';
import { config } from '@/lib/config';
import { logger } from '@/lib/logger';
import { withRetry } from '@/lib/retry';
import { AgentError } from '@/lib/errors';
import type OpenAI from 'openai';

interface AgentCallOptions {
    /** Temperature override. Default 0.2 (deterministic). Use higher for creative agents. */
    temperature?: number;
}

/** Parse a completion response into structured JSON. */
function parseResponse<T>(
    responseText: string,
    agentName: string,
    context: Record<string, unknown>
): T {
    try {
        return JSON.parse(responseText) as T;
    } catch {
        // Fallback: extract JSON from markdown-wrapped response
        const jsonMatch = responseText.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            return JSON.parse(jsonMatch[0]) as T;
        }
        throw new AgentError(
            `Failed to parse JSON response from ${agentName}`,
            agentName,
            { ...context, responsePreview: responseText.substring(0, 300) }
        );
    }
}

/** Make an LLM call to a specific client. */
async function callLLM<T>(
    client: OpenAI,
    model: string,
    systemPrompt: string,
    userPrompt: string,
    temperature: number,
    agentName: string,
    context: Record<string, unknown>
): Promise<T> {
    const completion = await client.chat.completions.create({
        model,
        messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt },
        ],
        temperature,
        response_format: { type: 'json_object' },
    });

    const responseText = completion.choices[0]?.message?.content || '{}';
    return parseResponse<T>(responseText, agentName, context);
}

/**
 * Shared utility for all Strategist Room sub-agents.
 * Makes an LLM call with a specialized prompt and returns parsed JSON.
 *
 * - Tries OpenRouter (Gemini Flash) first
 * - Falls back to K2 Think API if OpenRouter fails and K2 Think is configured
 * - Uses response_format: json_object for structured output
 * - Configurable temperature per agent (default 0.2)
 * - Retries up to 2 times with exponential backoff per provider
 */
export async function makeAgentCall<T>(
    agentName: string,
    systemPrompt: string,
    userPrompt: string,
    context: Record<string, unknown> = {},
    options: AgentCallOptions = {}
): Promise<T> {
    const { temperature = 0.2 } = options;

    logger.info(`${agentName}: Starting`, { ...context, temperature });

    // Try OpenRouter first
    try {
        const result = await withRetry(
            () => callLLM<T>(openRouter, config.openrouter.model, systemPrompt, userPrompt, temperature, agentName, context),
            agentName,
            { maxRetries: 2, baseDelayMs: 1000 }
        );
        logger.info(`${agentName}: Complete (OpenRouter)`, context);
        return result;
    } catch (primaryError) {
        // If K2 Think is configured, try it as fallback
        if (k2think) {
            const k2client = k2think;
            logger.warn(`${agentName}: OpenRouter failed, falling back to K2 Think`, {
                ...context,
                error: primaryError instanceof Error ? primaryError.message : String(primaryError),
            });

            try {
                const result = await withRetry(
                    () => callLLM<T>(k2client, config.k2think.model, systemPrompt, userPrompt, temperature, agentName, context),
                    `${agentName}[K2Think]`,
                    { maxRetries: 2, baseDelayMs: 1000 }
                );
                logger.info(`${agentName}: Complete (K2 Think fallback)`, context);
                return result;
            } catch (fallbackError) {
                logger.error(`${agentName}: K2 Think fallback also failed`, fallbackError instanceof Error ? fallbackError : new Error(String(fallbackError)));
                // Throw the original error since both failed
                throw primaryError;
            }
        }

        // No fallback available, rethrow original
        throw primaryError;
    }
}
