import { logger } from '@/lib/logger';
import { withRetry } from '@/lib/retry';
import { semanticScholarLimiter } from './rate-limiter';
import type { PaperMetadata } from './types';

const S2_API_BASE = 'https://api.semanticscholar.org/graph/v1';

const PAPER_FIELDS = [
    'title',
    'authors',
    'abstract',
    'year',
    'citationCount',
    'externalIds',
    'openAccessPdf',
    'fieldsOfStudy',
].join(',');

interface S2Author {
    name: string;
}

interface S2Paper {
    paperId: string;
    title: string;
    authors?: S2Author[];
    abstract?: string;
    year?: number;
    citationCount?: number;
    externalIds?: {
        ArXiv?: string;
        DOI?: string;
    };
    openAccessPdf?: {
        url: string;
    };
    fieldsOfStudy?: string[];
}

interface S2SearchResponse {
    total: number;
    data: S2Paper[];
}

function parsePaper(paper: S2Paper): PaperMetadata {
    return {
        semantic_scholar_id: paper.paperId,
        arxiv_id: paper.externalIds?.ArXiv || undefined,
        doi: paper.externalIds?.DOI || undefined,
        title: paper.title || '',
        authors: paper.authors?.map(a => a.name) || [],
        abstract: paper.abstract || '',
        published: paper.year ? String(paper.year) : '',
        pdf_url: paper.openAccessPdf?.url || undefined,
        categories: paper.fieldsOfStudy || [],
        citation_count: paper.citationCount ?? undefined,
        source: 'semantic_scholar',
    };
}

export async function searchPapers(
    query: string,
    limit: number = 10
): Promise<PaperMetadata[]> {
    await semanticScholarLimiter.acquire();

    const params = new URLSearchParams({
        query,
        limit: String(Math.min(limit, 25)),
        fields: PAPER_FIELDS,
    });

    const url = `${S2_API_BASE}/paper/search?${params.toString()}`;

    return withRetry(
        async () => {
            logger.info('Semantic Scholar search', { query, limit });

            const response = await fetch(url);

            if (response.status === 429) {
                throw new Error('Semantic Scholar rate limit exceeded');
            }

            if (!response.ok) {
                throw new Error(`Semantic Scholar API error: ${response.status} ${response.statusText}`);
            }

            const data: S2SearchResponse = await response.json();

            if (!data.data?.length) {
                return [];
            }

            const papers = data.data.map(parsePaper);
            logger.info('Semantic Scholar search results', { query, count: papers.length });
            return papers;
        },
        'searchPapers',
        { maxRetries: 2, baseDelayMs: 1000 }
    );
}

export async function getPaper(paperId: string): Promise<PaperMetadata | null> {
    await semanticScholarLimiter.acquire();

    // S2 accepts: S2 ID, DOI, ArXiv:{id}, PMID, etc.
    const url = `${S2_API_BASE}/paper/${encodeURIComponent(paperId)}?fields=${PAPER_FIELDS}`;

    return withRetry(
        async () => {
            logger.info('Semantic Scholar get paper', { paperId });

            const response = await fetch(url);

            if (response.status === 404) {
                logger.warn('Semantic Scholar paper not found', { paperId });
                return null;
            }

            if (response.status === 429) {
                throw new Error('Semantic Scholar rate limit exceeded');
            }

            if (!response.ok) {
                throw new Error(`Semantic Scholar API error: ${response.status} ${response.statusText}`);
            }

            const data: S2Paper = await response.json();
            return parsePaper(data);
        },
        'getPaper',
        { maxRetries: 2, baseDelayMs: 1000 }
    );
}
