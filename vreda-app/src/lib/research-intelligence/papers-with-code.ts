import { withRetry } from '@/lib/retry';
import { logger } from '@/lib/logger';
import { pwcLimiter } from '@/lib/literature/rate-limiter';
import type { PapersWithCodeResult } from '@/types/research-intelligence';

const PWC_API_BASE = 'https://paperswithcode.com/api/v1';

interface PwCPaperResponse {
    id: string;
    title: string;
    arxiv_id: string | null;
    url_abs: string | null;
}

interface PwCRepoResponse {
    url: string;
    owner: string;
    name: string;
    description: string;
    stars: number;
    framework: string | null;
    is_official: boolean;
}

interface PwCTaskResponse {
    id: string;
    name: string;
}

interface PwCMethodResponse {
    id: string;
    name: string;
}

/**
 * Look up a paper on Papers With Code by arXiv ID.
 * Returns repo listings, tasks, and methods.
 */
export async function lookupByArxivId(arxivId: string): Promise<PapersWithCodeResult | null> {
    await pwcLimiter.acquire();

    return withRetry(
        async () => {
            logger.info('Papers With Code lookup', { arxivId });

            // Step 1: Find the paper by arXiv ID
            const searchUrl = `${PWC_API_BASE}/papers/?arxiv_id=${encodeURIComponent(arxivId)}`;
            const searchRes = await fetch(searchUrl);

            if (!searchRes.ok) {
                if (searchRes.status === 404) return null;
                throw new Error(`PwC API error: ${searchRes.status}`);
            }

            const searchData = await searchRes.json();
            const results: PwCPaperResponse[] = searchData.results || [];

            if (!results.length) {
                logger.info('Paper not found on Papers With Code', { arxivId });
                return null;
            }

            const paper = results[0];
            const paperId = paper.id;

            // Step 2: Fetch repos, tasks, methods in parallel
            await pwcLimiter.acquire();
            const [reposRes, tasksRes, methodsRes] = await Promise.allSettled([
                fetch(`${PWC_API_BASE}/papers/${paperId}/repositories/`),
                fetch(`${PWC_API_BASE}/papers/${paperId}/tasks/`),
                fetch(`${PWC_API_BASE}/papers/${paperId}/methods/`),
            ]);

            const repos: PwCRepoResponse[] = reposRes.status === 'fulfilled' && reposRes.value.ok
                ? (await reposRes.value.json()).results || []
                : [];

            const tasks: PwCTaskResponse[] = tasksRes.status === 'fulfilled' && tasksRes.value.ok
                ? (await tasksRes.value.json()).results || []
                : [];

            const methods: PwCMethodResponse[] = methodsRes.status === 'fulfilled' && methodsRes.value.ok
                ? (await methodsRes.value.json()).results || []
                : [];

            logger.info('Papers With Code results', {
                arxivId,
                repos: repos.length,
                tasks: tasks.length,
                methods: methods.length,
            });

            return {
                paper_id: paperId,
                paper_title: paper.title,
                repositories: repos.map(r => ({
                    url: r.url,
                    stars: r.stars || 0,
                    framework: r.framework || null,
                    description: r.description || '',
                    is_official: r.is_official || false,
                })),
                tasks: tasks.map(t => t.name),
                methods: methods.map(m => m.name),
            };
        },
        'pwcLookup',
        { maxRetries: 2, baseDelayMs: 1000 }
    );
}
