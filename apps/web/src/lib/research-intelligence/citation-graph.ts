import { withRetry } from '@/lib/retry';
import { logger } from '@/lib/logger';
import { semanticScholarLimiter } from '@/lib/literature/rate-limiter';
import type { CitationGraph, CitationPaper, RelatedPaper } from '@/types/research-intelligence';

const S2_API_BASE = 'https://api.semanticscholar.org/graph/v1';
const S2_RECOMMEND_BASE = 'https://api.semanticscholar.org/recommendations/v1';

const CITATION_FIELDS = 'title,year,citationCount,externalIds,venue,isInfluential,fieldsOfStudy';

interface S2CitationEntry {
    citingPaper?: S2RefPaper;
    citedPaper?: S2RefPaper;
}

interface S2RefPaper {
    paperId: string;
    title: string;
    year?: number;
    citationCount?: number;
    externalIds?: { ArXiv?: string };
    venue?: string;
    isInfluential?: boolean;
    fieldsOfStudy?: string[];
}

function parseCitationPaper(paper: S2RefPaper, influential: boolean): CitationPaper {
    return {
        semantic_scholar_id: paper.paperId,
        title: paper.title || '',
        year: paper.year ?? null,
        citation_count: paper.citationCount ?? 0,
        arxiv_id: paper.externalIds?.ArXiv ?? null,
        venue: paper.venue ?? null,
        influential,
        fields_of_study: paper.fieldsOfStudy ?? [],
    };
}

/**
 * Fetch citation graph for a paper from Semantic Scholar.
 * Returns references (what this paper cites) and citations (what cites this paper).
 * Uses a single API call with expanded fields.
 */
export async function getCitationGraph(paperId: string): Promise<CitationGraph> {
    await semanticScholarLimiter.acquire();

    return withRetry(
        async () => {
            logger.info('Fetching citation graph', { paperId });

            // Fetch references and citations in parallel
            const [refsRes, citesRes] = await Promise.allSettled([
                fetch(
                    `${S2_API_BASE}/paper/${encodeURIComponent(paperId)}/references?fields=${CITATION_FIELDS}&limit=100`
                ),
                fetch(
                    `${S2_API_BASE}/paper/${encodeURIComponent(paperId)}/citations?fields=${CITATION_FIELDS}&limit=100`
                ),
            ]);

            // Parse references
            const references: CitationPaper[] = [];
            if (refsRes.status === 'fulfilled' && refsRes.value.ok) {
                const refsData = await refsRes.value.json();
                const entries: S2CitationEntry[] = refsData.data || [];
                for (const entry of entries) {
                    if (entry.citedPaper?.paperId) {
                        references.push(parseCitationPaper(entry.citedPaper, entry.citedPaper.isInfluential || false));
                    }
                }
            } else {
                logger.warn('Failed to fetch references', { paperId });
            }

            // Parse citations
            const citations: CitationPaper[] = [];
            if (citesRes.status === 'fulfilled' && citesRes.value.ok) {
                const citesData = await citesRes.value.json();
                const entries: S2CitationEntry[] = citesData.data || [];
                for (const entry of entries) {
                    if (entry.citingPaper?.paperId) {
                        citations.push(parseCitationPaper(entry.citingPaper, entry.citingPaper.isInfluential || false));
                    }
                }
            } else {
                logger.warn('Failed to fetch citations', { paperId });
            }

            const currentYear = new Date().getFullYear();

            const graph: CitationGraph = {
                references,
                citations,
                influential_citation_count: citations.filter(c => c.influential).length,
                total_citation_count: citations.length,
                reference_count: references.length,
                highly_cited_references: references
                    .filter(r => r.citation_count > 100)
                    .sort((a, b) => b.citation_count - a.citation_count)
                    .slice(0, 10),
                recent_citations: citations
                    .filter(c => c.year && c.year >= currentYear - 2)
                    .sort((a, b) => b.citation_count - a.citation_count)
                    .slice(0, 10),
            };

            logger.info('Citation graph complete', {
                paperId,
                references: references.length,
                citations: citations.length,
                highlyCited: graph.highly_cited_references.length,
            });

            return graph;
        },
        's2CitationGraph',
        { maxRetries: 2, baseDelayMs: 1500 }
    );
}

/**
 * Get recommended related papers from Semantic Scholar.
 */
export async function getRecommendations(paperId: string, limit: number = 10): Promise<RelatedPaper[]> {
    await semanticScholarLimiter.acquire();

    return withRetry(
        async () => {
            logger.info('Fetching S2 recommendations', { paperId, limit });

            const res = await fetch(`${S2_RECOMMEND_BASE}/papers/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    positivePaperIds: [paperId],
                    fields: 'title,year,citationCount,externalIds,abstract,venue',
                }),
            });

            if (!res.ok) {
                if (res.status === 429) {
                    logger.warn('S2 recommendations rate-limited', { paperId });
                    return [];
                }
                if (res.status === 404) return [];
                if (res.status >= 500) {
                    logger.warn('S2 recommendations upstream failure', { paperId, status: res.status });
                    return [];
                }
                throw new Error(`S2 Recommendations API error: ${res.status}`);
            }

            const data = await res.json();
            const papers: S2RefPaper[] = data.recommendedPapers || [];

            return papers.slice(0, limit).map((p): RelatedPaper => ({
                title: p.title || '',
                arxiv_id: p.externalIds?.ArXiv ?? null,
                semantic_scholar_id: p.paperId,
                year: p.year ?? null,
                citation_count: p.citationCount ?? 0,
                abstract: (p as { abstract?: string }).abstract || '',
                venue: p.venue ?? null,
                relevance_source: 'recommendation',
            }));
        },
        's2Recommendations',
        { maxRetries: 2, baseDelayMs: 1500 }
    );
}

/**
 * Search for related papers by keyword on Semantic Scholar.
 */
export async function searchRelated(query: string, limit: number = 5): Promise<RelatedPaper[]> {
    await semanticScholarLimiter.acquire();

    return withRetry(
        async () => {
            const params = new URLSearchParams({
                query,
                limit: String(limit),
                fields: 'title,year,citationCount,externalIds,abstract,venue',
            });

            const res = await fetch(`${S2_API_BASE}/paper/search?${params.toString()}`);

            if (!res.ok) {
                if (res.status === 429) {
                    logger.warn('S2 search rate-limited', { query: query.substring(0, 80) });
                    return [];
                }
                if (res.status >= 500) {
                    logger.warn('S2 search upstream failure', { status: res.status, query: query.substring(0, 80) });
                    return [];
                }
                throw new Error(`S2 search error: ${res.status}`);
            }

            const data = await res.json();
            const papers: (S2RefPaper & { abstract?: string })[] = data.data || [];

            return papers.map((p): RelatedPaper => ({
                title: p.title || '',
                arxiv_id: p.externalIds?.ArXiv ?? null,
                semantic_scholar_id: p.paperId,
                year: p.year ?? null,
                citation_count: p.citationCount ?? 0,
                abstract: p.abstract || '',
                venue: p.venue ?? null,
                relevance_source: 'keyword_search',
            }));
        },
        's2SearchRelated',
        { maxRetries: 2, baseDelayMs: 1500 }
    );
}
