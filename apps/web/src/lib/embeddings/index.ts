/**
 * Embeddings router — auto-selects provider based on configuration.
 * Priority: OpenAI (text-embedding-3-large) > Gemini (gemini-embedding-001)
 */
import { config } from '@/lib/config';
import { logger } from '@/lib/logger';
import * as openaiEmbeddings from './openai';
import * as geminiEmbeddings from './gemini';

export type { BatchEmbedResult, EmbeddingProgressCallback } from './gemini';

const useOpenAI = Boolean(config.openai.apiKey);

if (useOpenAI) {
    logger.info('Embeddings provider: OpenAI text-embedding-3-large');
} else {
    logger.info('Embeddings provider: Gemini gemini-embedding-001 (fallback)');
}

export const embedText: typeof geminiEmbeddings.embedText = useOpenAI
    ? openaiEmbeddings.embedText
    : geminiEmbeddings.embedText;

export const batchEmbedTexts: typeof geminiEmbeddings.batchEmbedTexts = useOpenAI
    ? openaiEmbeddings.batchEmbedTexts
    : geminiEmbeddings.batchEmbedTexts;
