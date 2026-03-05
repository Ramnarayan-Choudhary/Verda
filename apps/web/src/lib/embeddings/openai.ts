import OpenAI from 'openai';
import { config } from '@/lib/config';
import { withRetry } from '@/lib/retry';
import { EmbeddingError } from '@/lib/errors';
import { logger } from '@/lib/logger';
import type { BatchEmbedResult, EmbeddingProgressCallback } from './gemini';

const client = config.openai.apiKey ? new OpenAI({ apiKey: config.openai.apiKey }) : null;
const EMBEDDING_MODEL = config.openai.embeddingModel;
const EMBEDDING_DIMENSIONS = 768; // Match existing DB schema (pgvector + HNSW index)

/**
 * Embed a single text string using OpenAI text-embedding-3-large.
 * Returns a 768-dimensional vector (truncated via API to match DB schema).
 * Retries up to 3 times with exponential backoff on failure.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export async function embedText(text: string, taskType?: string): Promise<number[]> {
    if (!client) {
        throw new EmbeddingError('OpenAI client not configured — set OPENAI_API_KEY', {});
    }

    return withRetry(
        async () => {
            const result = await client.embeddings.create({
                model: EMBEDDING_MODEL,
                input: text,
                dimensions: EMBEDDING_DIMENSIONS,
            });
            return result.data[0]?.embedding ?? [];
        },
        'openai-embedText',
        { maxRetries: 3, baseDelayMs: 1000 }
    );
}

/**
 * Batch embed multiple text chunks using OpenAI embeddings API.
 * OpenAI supports up to 2048 inputs per request, so we batch in groups of 100.
 * Only throws EmbeddingError if ALL chunks fail.
 */
export async function batchEmbedTexts(
    texts: string[],
    onProgress?: EmbeddingProgressCallback
): Promise<BatchEmbedResult> {
    if (!client) {
        throw new EmbeddingError('OpenAI client not configured — set OPENAI_API_KEY', {});
    }

    const BATCH_SIZE = 100;
    const embeddings: (number[] | null)[] = new Array(texts.length).fill(null);
    const failedIndices: number[] = [];
    let processedCount = 0;

    logger.info('Starting OpenAI batch embedding', { totalChunks: texts.length, batchSize: BATCH_SIZE });

    const batches: { startIdx: number; texts: string[] }[] = [];
    for (let i = 0; i < texts.length; i += BATCH_SIZE) {
        batches.push({ startIdx: i, texts: texts.slice(i, i + BATCH_SIZE) });
    }

    for (let b = 0; b < batches.length; b++) {
        const batch = batches[b];

        try {
            const result = await withRetry(
                async () => {
                    return client!.embeddings.create({
                        model: EMBEDDING_MODEL,
                        input: batch.texts,
                        dimensions: EMBEDDING_DIMENSIONS,
                    });
                },
                `openai-embedBatch[${b + 1}/${batches.length}]`,
                { maxRetries: 3, baseDelayMs: 2000, maxDelayMs: 10000 }
            );

            for (let j = 0; j < batch.texts.length; j++) {
                const globalIdx = batch.startIdx + j;
                embeddings[globalIdx] = result.data[j]?.embedding ?? null;
                if (!embeddings[globalIdx]) {
                    failedIndices.push(globalIdx);
                }
            }
            processedCount += batch.texts.length;
            onProgress?.(processedCount, texts.length);
        } catch (batchError) {
            logger.warn(`OpenAI batch ${b + 1}/${batches.length} failed, trying individually`, {
                error: batchError instanceof Error ? batchError.message : String(batchError),
                batchStart: batch.startIdx,
                batchSize: batch.texts.length,
            });

            for (let j = 0; j < batch.texts.length; j++) {
                const globalIdx = batch.startIdx + j;
                try {
                    const result = await withRetry(
                        async () => client!.embeddings.create({
                            model: EMBEDDING_MODEL,
                            input: batch.texts[j],
                            dimensions: EMBEDDING_DIMENSIONS,
                        }),
                        `openai-embed[${globalIdx + 1}/${texts.length}]`,
                        { maxRetries: 3, baseDelayMs: 2000, maxDelayMs: 10000 }
                    );
                    embeddings[globalIdx] = result.data[0]?.embedding ?? null;
                    if (!embeddings[globalIdx]) failedIndices.push(globalIdx);
                } catch (error) {
                    logger.warn(`OpenAI embedding failed for chunk ${globalIdx + 1}/${texts.length}`, {
                        chunkIndex: globalIdx,
                        error: error instanceof Error ? error.message : String(error),
                    });
                    failedIndices.push(globalIdx);
                }
                processedCount++;
                onProgress?.(processedCount, texts.length);
            }
        }
    }

    const succeeded = texts.length - failedIndices.length;

    if (succeeded === 0) {
        throw new EmbeddingError(
            `All ${texts.length} chunks failed to embed with OpenAI`,
            { totalTexts: texts.length, failedIndices }
        );
    }

    logger.info('OpenAI batch embedding complete', {
        totalChunks: texts.length,
        succeeded,
        failed: failedIndices.length,
    });

    return { embeddings, succeeded, failed: failedIndices.length, failedIndices };
}
