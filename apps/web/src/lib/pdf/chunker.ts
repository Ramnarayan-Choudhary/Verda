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

// ============================================
// Semantic (Section-Aware) Chunking
// ============================================

const KNOWN_SECTIONS = [
    'abstract', 'introduction', 'background', 'related work',
    'methodology', 'methods', 'method', 'approach',
    'experiments', 'experimental setup', 'experimental results',
    'results', 'evaluation', 'discussion',
    'analysis', 'ablation', 'ablation study',
    'conclusion', 'conclusions', 'future work',
    'acknowledgements', 'acknowledgments', 'references', 'appendix',
    'supplementary', 'supplementary material',
];

/** Check if a line looks like a section header in an academic paper. */
function isSectionHeader(line: string): boolean {
    const trimmed = line.trim();
    if (!trimmed || trimmed.length > 120) return false;

    // Markdown headers: ## Introduction
    if (/^#{1,4}\s+\S/.test(trimmed)) return true;

    // Numbered sections: 1. Introduction, 1 Introduction, 2.1 Methods
    if (/^\d+\.?\d*\.?\s+[A-Z]/.test(trimmed)) return true;

    // ALL CAPS lines (min 3 chars, max 60): INTRODUCTION, RELATED WORK
    if (/^[A-Z][A-Z\s&:]{2,59}$/.test(trimmed)) return true;

    // Known section names (case-insensitive, with optional numbering prefix)
    const normalized = trimmed.replace(/^[\d.]+\s*/, '').replace(/^#+\s*/, '').toLowerCase();
    if (KNOWN_SECTIONS.includes(normalized)) return true;

    return false;
}

interface Section {
    header: string;
    content: string;
}

/** Split text into sections based on detected headers. */
function splitIntoSections(text: string): Section[] {
    const lines = text.split('\n');
    const sections: Section[] = [];
    let currentHeader = 'Preamble';
    let currentLines: string[] = [];

    for (const line of lines) {
        if (isSectionHeader(line)) {
            // Save previous section
            if (currentLines.length > 0) {
                sections.push({
                    header: currentHeader,
                    content: currentLines.join('\n').trim(),
                });
            }
            currentHeader = line.trim().replace(/^[\d.]+\s*/, '').replace(/^#+\s*/, '').trim();
            currentLines = [];
        } else {
            currentLines.push(line);
        }
    }

    // Save last section
    if (currentLines.length > 0) {
        sections.push({
            header: currentHeader,
            content: currentLines.join('\n').trim(),
        });
    }

    return sections.filter(s => s.content.length > 0);
}

/**
 * Section-aware chunking for academic papers.
 * Detects section boundaries and prefixes each chunk with its section name.
 * Falls back to basic chunkText() if fewer than 2 sections are detected.
 */
export function semanticChunkText(
    text: string,
    options: ChunkOptions = {}
): string[] {
    const {
        chunkSize = 1000,
        chunkOverlap = 200,
    } = options;

    const sections = splitIntoSections(text);

    // Fallback: if we can't detect sections, use basic chunking
    if (sections.length < 2) {
        return chunkText(text, options);
    }

    const chunks: string[] = [];

    for (const section of sections) {
        const prefix = `[${section.header}] `;

        // If the whole section fits in one chunk, use it directly
        if (prefix.length + section.content.length <= chunkSize) {
            chunks.push(`${prefix}${section.content}`.trim());
            continue;
        }

        // Split section content into paragraphs
        const paragraphs = section.content.split(/\n\s*\n/).filter(p => p.trim());
        let currentChunk = prefix;

        for (const paragraph of paragraphs) {
            const candidate = currentChunk.length > prefix.length
                ? currentChunk + '\n\n' + paragraph
                : currentChunk + paragraph;

            if (candidate.length > chunkSize && currentChunk.length > prefix.length) {
                chunks.push(currentChunk.trim());
                // Carry overlap into next chunk
                const overlap = currentChunk.slice(-chunkOverlap);
                currentChunk = prefix + overlap + '\n\n' + paragraph;
            } else if (paragraph.length + prefix.length > chunkSize) {
                // Single paragraph too large — use basic chunker for it
                if (currentChunk.length > prefix.length) {
                    chunks.push(currentChunk.trim());
                }
                const subChunks = chunkText(paragraph, { chunkSize: chunkSize - prefix.length, chunkOverlap });
                for (const sub of subChunks) {
                    chunks.push(`${prefix}${sub}`.trim());
                }
                currentChunk = prefix;
            } else {
                currentChunk = candidate;
            }
        }

        if (currentChunk.trim().length > prefix.length) {
            chunks.push(currentChunk.trim());
        }
    }

    return chunks;
}

/**
 * Section-aware chunking with indices for tracking.
 */
export function semanticChunkTextWithIndices(
    text: string,
    options?: ChunkOptions
): { content: string; index: number }[] {
    return semanticChunkText(text, options).map((content, index) => ({
        content,
        index,
    }));
}
