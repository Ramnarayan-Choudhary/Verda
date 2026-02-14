import { lookupByArxivId } from './papers-with-code';
import { getRepoMetrics } from './github';
import { getCitationGraph, getRecommendations, searchRelated } from './citation-graph';
import { logger } from '@/lib/logger';
import type { PaperAnalysis } from '@/types/strategist';
import type {
    ResearchIntelligence,
    CodeDiscovery,
    CitationGraph,
    RelatedWork,
    RepoMetrics,
} from '@/types/research-intelligence';

export type ProgressCallback = (step: string, message: string) => void;

const EMPTY_CODE_DISCOVERY: CodeDiscovery = {
    papers_with_code: null,
    repos: [],
    best_repo: null,
    total_repos_found: 0,
    source: 'none',
};

const EMPTY_CITATION_GRAPH: CitationGraph = {
    references: [],
    citations: [],
    influential_citation_count: 0,
    total_citation_count: 0,
    reference_count: 0,
    highly_cited_references: [],
    recent_citations: [],
};

const EMPTY_RELATED_WORK: RelatedWork = {
    papers: [],
    research_landscape_size: 0,
};

/**
 * Gather code discovery data from Papers With Code + GitHub.
 */
async function gatherCodeDiscovery(
    arxivId: string | null,
    onProgress?: ProgressCallback
): Promise<CodeDiscovery> {
    if (!arxivId) return EMPTY_CODE_DISCOVERY;

    onProgress?.('research_intelligence', 'Searching Papers With Code for repositories...');

    const pwcResult = await lookupByArxivId(arxivId);
    if (!pwcResult || !pwcResult.repositories.length) {
        return { ...EMPTY_CODE_DISCOVERY, papers_with_code: pwcResult };
    }

    // Enrich top repos with GitHub metrics (max 3 to conserve rate limit)
    onProgress?.('research_intelligence', `Found ${pwcResult.repositories.length} repos, checking GitHub metrics...`);

    const repoUrls = pwcResult.repositories
        .sort((a, b) => b.stars - a.stars)
        .slice(0, 3)
        .map(r => r.url);

    const metricsResults = await Promise.allSettled(
        repoUrls.map(url => getRepoMetrics(url))
    );

    const repos: RepoMetrics[] = [];
    for (const result of metricsResults) {
        if (result.status === 'fulfilled' && result.value) {
            repos.push(result.value);
        }
    }

    // Pick best repo by health score
    const best_repo = repos.length
        ? repos.reduce((best, r) => r.health_score > best.health_score ? r : best, repos[0])
        : null;

    return {
        papers_with_code: pwcResult,
        repos,
        best_repo,
        total_repos_found: pwcResult.repositories.length,
        source: 'papers_with_code',
    };
}

/**
 * Gather citation graph from Semantic Scholar.
 */
async function gatherCitationGraphData(
    arxivId: string | null,
    s2Id: string | null,
    onProgress?: ProgressCallback
): Promise<CitationGraph> {
    const paperId = s2Id || (arxivId ? `ArXiv:${arxivId}` : null);
    if (!paperId) return EMPTY_CITATION_GRAPH;

    onProgress?.('research_intelligence', 'Fetching citation graph...');
    return getCitationGraph(paperId);
}

/**
 * Gather related work from S2 recommendations + keyword search.
 */
async function gatherRelatedWorkData(
    arxivId: string | null,
    s2Id: string | null,
    paperAnalysis: PaperAnalysis,
    onProgress?: ProgressCallback
): Promise<RelatedWork> {
    const paperId = s2Id || (arxivId ? `ArXiv:${arxivId}` : null);

    onProgress?.('research_intelligence', 'Discovering related papers...');

    // Run recommendations + keyword search in parallel
    const searchQuery = `${paperAnalysis.title} ${paperAnalysis.domain}`.substring(0, 100);

    const [recResult, searchResult] = await Promise.allSettled([
        paperId ? getRecommendations(paperId, 8) : Promise.resolve([]),
        searchRelated(searchQuery, 5),
    ]);

    const recommended = recResult.status === 'fulfilled' ? recResult.value : [];
    const searched = searchResult.status === 'fulfilled' ? searchResult.value : [];

    // Merge and deduplicate by S2 ID
    const seen = new Set<string>();
    const allPapers = [...recommended, ...searched].filter(p => {
        if (seen.has(p.semantic_scholar_id)) return false;
        seen.add(p.semantic_scholar_id);
        return true;
    });

    // Sort by citation count (most influential first)
    allPapers.sort((a, b) => b.citation_count - a.citation_count);

    return {
        papers: allPapers.slice(0, 10),
        research_landscape_size: allPapers.length,
    };
}

/**
 * Main entry point: Gather all research intelligence in parallel.
 * Each source failing is non-fatal — returns partial results.
 */
export async function gatherResearchIntelligence(
    paperAnalysis: PaperAnalysis,
    arxivId: string | null,
    s2Id: string | null,
    onProgress?: ProgressCallback
): Promise<ResearchIntelligence> {
    const start = Date.now();
    const errors: ResearchIntelligence['errors'] = [];

    logger.info('Gathering research intelligence', {
        arxivId,
        s2Id,
        title: paperAnalysis.title.substring(0, 80),
    });

    onProgress?.('research_intelligence', 'Gathering external research data...');

    // Run all three in parallel
    const [codeResult, citationResult, relatedResult] = await Promise.allSettled([
        gatherCodeDiscovery(arxivId, onProgress),
        gatherCitationGraphData(arxivId, s2Id, onProgress),
        gatherRelatedWorkData(arxivId, s2Id, paperAnalysis, onProgress),
    ]);

    // Extract with fallbacks
    let code_discovery = EMPTY_CODE_DISCOVERY;
    if (codeResult.status === 'fulfilled') {
        code_discovery = codeResult.value;
    } else {
        errors.push({ source: 'papers_with_code', message: codeResult.reason?.message || 'Unknown error' });
        logger.warn('Code discovery failed (non-fatal)', { error: codeResult.reason?.message });
    }

    let citation_graph = EMPTY_CITATION_GRAPH;
    if (citationResult.status === 'fulfilled') {
        citation_graph = citationResult.value;
    } else {
        errors.push({ source: 'semantic_scholar_citations', message: citationResult.reason?.message || 'Unknown error' });
        logger.warn('Citation graph failed (non-fatal)', { error: citationResult.reason?.message });
    }

    let related_work = EMPTY_RELATED_WORK;
    if (relatedResult.status === 'fulfilled') {
        related_work = relatedResult.value;
    } else {
        errors.push({ source: 'semantic_scholar_related', message: relatedResult.reason?.message || 'Unknown error' });
        logger.warn('Related work failed (non-fatal)', { error: relatedResult.reason?.message });
    }

    const latency_ms = Date.now() - start;

    logger.info('Research intelligence complete', {
        arxivId,
        repos: code_discovery.total_repos_found,
        references: citation_graph.reference_count,
        citations: citation_graph.total_citation_count,
        relatedPapers: related_work.papers.length,
        errors: errors.length,
        latency_ms,
    });

    onProgress?.('research_intelligence', `Found ${code_discovery.total_repos_found} repos, ${citation_graph.reference_count} references, ${related_work.papers.length} related papers`);

    return {
        code_discovery,
        citation_graph,
        related_work,
        paper_arxiv_id: arxivId,
        paper_s2_id: s2Id,
        paper_title: paperAnalysis.title,
        gathered_at: new Date().toISOString(),
        latency_ms,
        errors,
    };
}
