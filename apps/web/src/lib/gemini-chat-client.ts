import OpenAI from 'openai';
import { config } from './config';

// Gemini exposes an OpenAI-compatible REST endpoint
export const geminiChat = config.gemini.apiKey
    ? new OpenAI({
        baseURL: 'https://generativelanguage.googleapis.com/v1beta/openai/',
        apiKey: config.gemini.apiKey,
    })
    : null;
