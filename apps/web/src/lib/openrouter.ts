import OpenAI from 'openai';
import { config } from './config';

export const openRouter = config.openrouter.apiKey
    ? new OpenAI({
        baseURL: 'https://openrouter.ai/api/v1',
        apiKey: config.openrouter.apiKey,
        defaultHeaders: {
            'HTTP-Referer': config.app.url,
            'X-Title': 'VREDA.ai',
        },
    })
    : null;
