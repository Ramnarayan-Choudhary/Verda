import OpenAI from 'openai';
import { config } from './config';

/**
 * DeepSeek API client (OpenAI-compatible).
 * Returns null when no DEEPSEEK_API_KEY is configured.
 */
export const deepseek = config.deepseek.apiKey
    ? new OpenAI({
        baseURL: config.deepseek.baseUrl,
        apiKey: config.deepseek.apiKey,
    })
    : null;
