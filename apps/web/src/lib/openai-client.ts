import OpenAI from 'openai';
import { config } from './config';

/**
 * OpenAI API client (direct, not via proxy).
 * Used as primary provider for best reasoning quality (GPT-4o).
 * Returns null when no OPENAI_API_KEY is configured.
 */
export const openaiClient = config.openai.apiKey
    ? new OpenAI({
        apiKey: config.openai.apiKey,
    })
    : null;
