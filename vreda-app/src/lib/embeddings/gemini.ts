import { GoogleGenAI } from '@google/genai';
import { config } from '@/lib/config';
import { withRetry } from '@/lib/retry';
import { EmbeddingError } from '@/lib/errors';
import { logger } from '@/lib/logger';

const genai = new GoogleGenAI({ apiKey: config.gemini.apiKey });
const EMBEDDING_MODEL = 'gemini-embedding-001';
const EMBEDDING_DIMENSIONS = 768;

/**
 * Task types for Gemini embeddings.
 * Using the correct task type improves retrieval quality by ~5-10%.
 * - RETRIEVAL_DOCUMENT: for text being stored/indexed
 * - RETRIEVAL_QUERY: for search queries against stored text
 */
type EmbeddingTaskType = 'RETRIEVAL_DOCUMENT' | 'RETRIEVAL_QUERY';

/** Result of a batch embedding with partial-success support. */
export interface BatchEmbedResult {
    /** Embeddings array — null for chunks that failed after retries. */
    embeddings: (number[] | null)[];
    /** Number of chunks that embedded successfully. */
    succeeded: number;
    /** Number of chunks that failed after retries. */
    failed: number;
    /** Indices of failed chunks. */
    failedIndices: number[];
}

/** Progress callback for batch embedding. */
export type EmbeddingProgressCallback = (current: number, total: number) => void;

/**
 * Embed a single text string using gemini-embedding-001.
 * Returns a 768-dimensional vector (MRL to match our DB schema).
 * Retries up to 3 times with exponential backoff on failure.
 *
 * @param taskType - Use 'RETRIEVAL_QUERY' for search queries (default),
 *                   'RETRIEVAL_DOCUMENT' for storing/indexing text.
 */
export async function embedText(
    text: string,
    taskType: EmbeddingTaskType = 'RETRIEVAL_QUERY'
): Promise<number[]> {
    return withRetry(
        async () => {
            const result = await genai.models.embedContent({
                model: EMBEDDING_MODEL,
                contents: text,
                config: {
                    outputDimensionality: EMBEDDING_DIMENSIONS,
                    taskType,
                },
            });
            return result.embeddings?.[0]?.values ?? [];
        },
        'embedText',
        { maxRetries: 3, baseDelayMs: 1000 }
    );
}

/**
 * Batch embed multiple text chunks for document storage.
 * Uses Gemini's batch embedding (multiple texts per API call) to minimize
 * rate limit issues. Falls back to individual embedding on batch failure.
 * Only throws EmbeddingError if ALL chunks fail.
 *
 * @param onProgress - Optional callback fired as chunks complete.
 */
export async function batchEmbedTexts(
    texts: string[],
    onProgress?: EmbeddingProgressCallback
): Promise<BatchEmbedResult> {
    const BATCH_SIZE = 10;
    const DELAY_BETWEEN_BATCHES_MS = 1500;
    const embeddings: (number[] | null)[] = new Array(texts.length).fill(null);
    const failedIndices: number[] = [];
    let processedCount = 0;

    logger.info('Starting batch embedding', { totalChunks: texts.length, batchSize: BATCH_SIZE });

    // Split into batches
    const batches: { startIdx: number; texts: string[] }[] = [];
    for (let i = 0; i < texts.length; i += BATCH_SIZE) {
        batches.push({ startIdx: i, texts: texts.slice(i, i + BATCH_SIZE) });
    }

    for (let b = 0; b < batches.length; b++) {
        const batch = batches[b];

        try {
            // Try batch API call (multiple texts in one request)
            const result = await withRetry(
                async () => {
                    return genai.models.embedContent({
                        model: EMBEDDING_MODEL,
                        contents: batch.texts,
                        config: {
                            outputDimensionality: EMBEDDING_DIMENSIONS,
                            taskType: 'RETRIEVAL_DOCUMENT' as EmbeddingTaskType,
                        },
                    });
                },
                `embedBatch[${b + 1}/${batches.length}]`,
                { maxRetries: 3, baseDelayMs: 3000, maxDelayMs: 12000 }
            );

            // Map results back to correct indices
            const batchEmbeddings = result.embeddings || [];
            for (let j = 0; j < batch.texts.length; j++) {
                const globalIdx = batch.startIdx + j;
                embeddings[globalIdx] = batchEmbeddings[j]?.values ?? null;
                if (!embeddings[globalIdx]) {
                    failedIndices.push(globalIdx);
                }
            }
            processedCount += batch.texts.length;
            onProgress?.(processedCount, texts.length);
        } catch (batchError) {
            // Batch failed — fall back to individual embedding for this batch
            logger.warn(`Batch ${b + 1}/${batches.length} failed, trying individually`, {
                error: batchError instanceof Error ? batchError.message : String(batchError),
                batchStart: batch.startIdx,
                batchSize: batch.texts.length,
            });

            for (let j = 0; j < batch.texts.length; j++) {
                const globalIdx = batch.startIdx + j;
                try {
                    const result = await withRetry(
                        async () => genai.models.embedContent({
                            model: EMBEDDING_MODEL,
                            contents: batch.texts[j],
                            config: {
                                outputDimensionality: EMBEDDING_DIMENSIONS,
                                taskType: 'RETRIEVAL_DOCUMENT' as EmbeddingTaskType,
                            },
                        }),
                        `embed[${globalIdx + 1}/${texts.length}]`,
                        { maxRetries: 3, baseDelayMs: 4000, maxDelayMs: 16000 }
                    );
                    embeddings[globalIdx] = result.embeddings?.[0]?.values ?? null;
                    if (!embeddings[globalIdx]) failedIndices.push(globalIdx);
                } catch (error) {
                    logger.warn(`Embedding failed for chunk ${globalIdx + 1}/${texts.length}, continuing`, {
                        chunkIndex: globalIdx,
                        error: error instanceof Error ? error.message : String(error),
                    });
                    failedIndices.push(globalIdx);
                }
                processedCount++;
                onProgress?.(processedCount, texts.length);

                // Small delay between individual fallback calls
                if (j < batch.texts.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 2000));
                }
            }
        }

        // Delay between batches to respect rate limits
        if (b < batches.length - 1) {
            await new Promise(resolve => setTimeout(resolve, DELAY_BETWEEN_BATCHES_MS));
        }
    }

    const succeeded = texts.length - failedIndices.length;

    if (succeeded === 0) {
        throw new EmbeddingError(
            `All ${texts.length} chunks failed to embed`,
            { totalTexts: texts.length, failedIndices }
        );
    }

    logger.info('Batch embedding complete', {
        totalChunks: texts.length,
        succeeded,
        failed: failedIndices.length,
    });

    return { embeddings, succeeded, failed: failedIndices.length, failedIndices };
}
