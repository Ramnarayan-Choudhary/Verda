/**
 * Recursive character text splitter for chunking documents.
 * Splits text into chunks of ~chunkSize characters with overlap.
 */

interface ChunkOptions {
    chunkSize?: number;
    chunkOverlap?: number;
    separators?: string[];
}

export function chunkText(
    text: string,
    options: ChunkOptions = {}
): string[] {
    const {
        chunkSize = 1000,
        chunkOverlap = 200,
        separators = ['\n\n', '\n', '. ', ' ', ''],
    } = options;

    if (text.length <= chunkSize) {
        return [text.trim()].filter(Boolean);
    }

    const chunks: string[] = [];
    let currentSep = separators[0];

    // Find the best separator that actually splits the text
    for (const sep of separators) {
        if (text.includes(sep)) {
            currentSep = sep;
            break;
        }
    }

    const splits = text.split(currentSep).filter(Boolean);
    let currentChunk = '';

    for (const split of splits) {
        const candidate = currentChunk
            ? currentChunk + currentSep + split
            : split;

        if (candidate.length > chunkSize && currentChunk) {
            chunks.push(currentChunk.trim());
            // Keep overlap from end of current chunk
            const overlapText = currentChunk.slice(-chunkOverlap);
            currentChunk = overlapText + currentSep + split;
        } else {
            currentChunk = candidate;
        }
    }

    if (currentChunk.trim()) {
        chunks.push(currentChunk.trim());
    }

    return chunks;
}

/**
 * Chunk text and return with indices for tracking.
 */
export function chunkTextWithIndices(
    text: string,
    options?: ChunkOptions
): { content: string; index: number }[] {
    return chunkText(text, options).map((content, index) => ({
        content,
        index,
    }));
}
