import OpenAI from 'openai';
import { config } from './config';

/**
 * K2 Think API client (OpenAI-compatible).
 * Used as a fallback LLM when OpenRouter/Gemini is unavailable.
 * Returns null if no API key is configured.
 */
export const k2think = config.k2think.apiKey
    ? new OpenAI({
        baseURL: config.k2think.baseUrl,
        apiKey: config.k2think.apiKey,
    })
    : null;
