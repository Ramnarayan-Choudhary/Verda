import { XMLParser } from 'fast-xml-parser';
import { logger } from '@/lib/logger';
import { withRetry } from '@/lib/retry';
import { arxivLimiter } from './rate-limiter';
import type { PaperMetadata } from './types';

const ARXIV_API_BASE = 'http://export.arxiv.org/api/query';
const ARXIV_PDF_BASE = 'https://export.arxiv.org/pdf';

// arXiv ID pattern: e.g., 2301.07041 or 2301.07041v2
const ARXIV_ID_REGEX = /^(\d{4}\.\d{4,5})(v\d+)?$/;

const xmlParser = new XMLParser({
    ignoreAttributes: false,
    attributeNamePrefix: '@_',
    isArray: (name) => name === 'entry' || name === 'author' || name === 'category',
});

interface ArxivEntry {
    id: string;
    title: string;
    summary: string;
    published: string;
    updated: string;
    author: Array<{ name: string }> | { name: string };
    category: Array<{ '@_term': string }> | { '@_term': string };
    'arxiv:doi'?: string;
}

interface ArxivResponse {
    feed: {
        entry?: ArxivEntry | ArxivEntry[];
        'opensearch:totalResults': string | number;
    };
}

function normalizeArxivId(input: string): string {
    // Strip 'arxiv:' prefix if present
    const cleaned = input.replace(/^arxiv:/i, '').trim();
    // Strip version suffix for lookup
    return cleaned.replace(/v\d+$/, '');
}

function parseEntry(entry: ArxivEntry): PaperMetadata {
    const idUrl = typeof entry.id === 'string' ? entry.id : '';
    const arxivId = idUrl.split('/abs/').pop()?.replace(/v\d+$/, '') || '';

    const authors = Array.isArray(entry.author)
        ? entry.author.map(a => a.name)
        : entry.author ? [entry.author.name] : [];

    const categories = Array.isArray(entry.category)
        ? entry.category.map(c => c['@_term'])
        : entry.category ? [entry.category['@_term']] : [];

    const title = typeof entry.title === 'string'
        ? entry.title.replace(/\s+/g, ' ').trim()
        : '';

    const abstract = typeof entry.summary === 'string'
        ? entry.summary.replace(/\s+/g, ' ').trim()
        : '';

    return {
        arxiv_id: arxivId,
        title,
        authors,
        abstract,
        published: entry.published || '',
        pdf_url: arxivId ? `${ARXIV_PDF_BASE}/${arxivId}` : undefined,
        categories,
        source: 'arxiv',
    };
}

export async function searchArxiv(
    query: string,
    maxResults: number = 10
): Promise<PaperMetadata[]> {
    await arxivLimiter.acquire();

    const params = new URLSearchParams({
        search_query: `all:${query}`,
        start: '0',
        max_results: String(Math.min(maxResults, 25)),
        sortBy: 'relevance',
        sortOrder: 'descending',
    });

    const url = `${ARXIV_API_BASE}?${params.toString()}`;

    return withRetry(
        async () => {
            logger.info('arXiv search', { query, maxResults });

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`arXiv API error: ${response.status} ${response.statusText}`);
            }

            const xml = await response.text();
            const parsed: ArxivResponse = xmlParser.parse(xml);

            if (!parsed.feed?.entry) {
                return [];
            }

            const entries = Array.isArray(parsed.feed.entry)
                ? parsed.feed.entry
                : [parsed.feed.entry];

            const papers = entries.map(parseEntry);
            logger.info('arXiv search results', { query, count: papers.length });
            return papers;
        },
        'searchArxiv',
        { maxRetries: 2, baseDelayMs: 3000 }
    );
}

export async function fetchByArxivId(id: string): Promise<PaperMetadata | null> {
    const normalized = normalizeArxivId(id);

    if (!ARXIV_ID_REGEX.test(normalized)) {
        logger.warn('Invalid arXiv ID format', { id, normalized });
        return null;
    }

    await arxivLimiter.acquire();

    const params = new URLSearchParams({
        id_list: normalized,
    });

    const url = `${ARXIV_API_BASE}?${params.toString()}`;

    return withRetry(
        async () => {
            logger.info('arXiv fetch by ID', { id: normalized });

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`arXiv API error: ${response.status} ${response.statusText}`);
            }

            const xml = await response.text();
            const parsed: ArxivResponse = xmlParser.parse(xml);

            if (!parsed.feed?.entry) {
                logger.warn('arXiv paper not found', { id: normalized });
                return null;
            }

            const entries = Array.isArray(parsed.feed.entry)
                ? parsed.feed.entry
                : [parsed.feed.entry];

            // Check if it's a valid entry (not an error response)
            const entry = entries[0];
            if (!entry.title || entry.title === 'Error') {
                return null;
            }

            return parseEntry(entry);
        },
        'fetchByArxivId',
        { maxRetries: 2, baseDelayMs: 3000 }
    );
}

export function isArxivId(text: string): boolean {
    const cleaned = text.replace(/^arxiv:/i, '').trim();
    return ARXIV_ID_REGEX.test(cleaned);
}

export { normalizeArxivId };
