import { openaiClient } from '@/lib/openai-client';
import { openRouter } from '@/lib/openrouter';
import { deepseek } from '@/lib/deepseek';
import { k2think } from '@/lib/k2think';
import { config } from '@/lib/config';
import { logger } from '@/lib/logger';
import { withRetry } from '@/lib/retry';
import { AgentError } from '@/lib/errors';
import { AGENT_SCHEMAS } from './schemas';
import type OpenAI from 'openai';
import type { ZodType, ZodError } from 'zod';

interface AgentCallOptions {
    /** Temperature override. Default 0.2 (deterministic). Use higher for creative agents. */
    temperature?: number;
    /** Hard cap to avoid provider defaults that can request very large completions. */
    maxTokens?: number;
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

/** Format Zod validation errors into a human-readable string for LLM retry prompts. */
function formatValidationErrors(zodError: ZodError): string {
    return zodError.issues.map(issue => {
        const path = issue.path.join('.');
        return `- ${path || 'root'}: ${issue.message}`;
    }).join('\n');
}

/** Parse a completion response into structured JSON and validate against Zod schema. */
function parseResponse<T>(
    responseText: string,
    agentName: string,
    context: Record<string, unknown>
): T {
    let parsed: unknown;

    try {
        parsed = JSON.parse(responseText);
    } catch {
        // Fallback: extract JSON from markdown-wrapped response
        const jsonMatch = responseText.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            parsed = JSON.parse(jsonMatch[0]);
        } else {
            throw new AgentError(
                `Failed to parse JSON response from ${agentName}`,
                agentName,
                { ...context, responsePreview: responseText.substring(0, 300) }
            );
        }
    }

    // Validate against Zod schema if one exists for this agent
    const schema: ZodType | undefined = AGENT_SCHEMAS[agentName];
    if (schema) {
        const result = schema.safeParse(parsed);
        if (!result.success) {
            const errorDetails = formatValidationErrors(result.error);
            throw new AgentError(
                `Schema validation failed for ${agentName}:\n${errorDetails}`,
                agentName,
                {
                    ...context,
                    validationErrors: result.error.issues,
                    responsePreview: JSON.stringify(parsed).substring(0, 500),
                }
            );
        }
        return result.data as T;
    }

    return parsed as T;
}

/** Make a single LLM call to a specific client. */
async function callLLM(
    client: OpenAI,
    model: string,
    systemPrompt: string,
    userPrompt: string,
    temperature: number,
    maxTokens: number,
): Promise<string> {
    const create = (tokenLimit: number) =>
        client.chat.completions.create({
            model,
            messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt },
            ],
            temperature,
            max_tokens: tokenLimit,
            response_format: { type: 'json_object' },
        });

    try {
        const completion = await create(maxTokens);
        return completion.choices[0]?.message?.content || '{}';
    } catch (error) {
        const affordable = extractAffordableTokens(error);
        if (affordable && affordable < maxTokens) {
            const retryLimit = Math.max(800, affordable - 120);
            const completion = await create(retryLimit);
            return completion.choices[0]?.message?.content || '{}';
        }
        throw error;
    }
}

/** Attempt a call with a specific provider, with retry. */
async function attemptCall<T>(
    client: OpenAI,
    model: string,
    systemPrompt: string,
    userPrompt: string,
    temperature: number,
    maxTokens: number,
    agentName: string,
    providerLabel: string,
    context: Record<string, unknown>
): Promise<T> {
    return withRetry(
        async () => {
            const responseText = await callLLM(
                client, model, systemPrompt, userPrompt, temperature, maxTokens,
            );
            return parseResponse<T>(responseText, agentName, context);
        },
        `${agentName}[${providerLabel}]`,
        { maxRetries: 2, baseDelayMs: 1000 }
    );
}

/**
 * Shared utility for all Strategist Room sub-agents.
 * Makes an LLM call with a specialized prompt and returns parsed + validated JSON.
 *
 * - Tries OpenRouter (Gemini Flash) first
 * - Falls back to K2 Think API if OpenRouter fails and K2 Think is configured
 * - Uses response_format: json_object for structured output
 * - Validates output against Zod schema (retries once with fix prompt on validation failure)
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
    const { temperature = 0.2, maxTokens = 4000 } = options;

    logger.info(`${agentName}: Starting`, { ...context, temperature, maxTokens });

    // First attempt: normal call
    try {
        const result = await attemptWithFallback<T>(
            systemPrompt, userPrompt, temperature, maxTokens, agentName, context
        );
        logger.info(`${agentName}: Complete`, context);
        return result;
    } catch (firstError) {
        // If it's a schema validation error, retry once with a fix prompt
        if (firstError instanceof AgentError && firstError.message.includes('Schema validation failed')) {
            logger.warn(`${agentName}: Schema validation failed, retrying with fix prompt`, {
                ...context,
                error: firstError.message,
            });

            const fixPrompt = `${userPrompt}\n\n---\nIMPORTANT: Your previous response had validation errors. Please fix these issues and return valid JSON:\n${firstError.message}`;

            try {
                const result = await attemptWithFallback<T>(
                    systemPrompt, fixPrompt, temperature, maxTokens, agentName, context
                );
                logger.info(`${agentName}: Complete (after validation fix)`, context);
                return result;
            } catch (retryError) {
                logger.error(`${agentName}: Validation retry also failed`, retryError instanceof Error ? retryError : new Error(String(retryError)));
                throw firstError; // Throw the original error for clarity
            }
        }

        throw firstError;
    }
}

/** Try OpenRouter first, then K2Think fallback. */
async function attemptWithFallback<T>(
    systemPrompt: string,
    userPrompt: string,
    temperature: number,
    maxTokens: number,
    agentName: string,
    context: Record<string, unknown>
): Promise<T> {
    const providers: Array<{ label: string; client: OpenAI; model: string }> = [];

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

    if (providers.length === 0) {
        throw new AgentError(
            'No LLM providers configured. Set DEEPSEEK_API_KEY, OPENROUTER_API_KEY, or K2THINK_API_KEY.',
            agentName,
            context
        );
    }

    let lastError: unknown = null;
    for (let i = 0; i < providers.length; i++) {
        const provider = providers[i];
        try {
            return await attemptCall<T>(
                provider.client,
                provider.model,
                systemPrompt,
                userPrompt,
                temperature,
                maxTokens,
                agentName,
                provider.label,
                context
            );
        } catch (error) {
            lastError = error;
            const isLast = i === providers.length - 1;
            if (!isLast) {
                logger.warn(`${agentName}: ${provider.label} failed, trying next provider`, {
                    ...context,
                    error: error instanceof Error ? error.message : String(error),
                });
            }
        }
    }

    throw lastError instanceof Error ? lastError : new Error(String(lastError));
}
