// ============================================
// Literature API Type Definitions
// ============================================

export interface PaperMetadata {
    arxiv_id?: string;
    semantic_scholar_id?: string;
    doi?: string;
    title: string;
    authors: string[];
    abstract: string;
    published: string;
    pdf_url?: string;
    categories: string[];
    citation_count?: number;
    influential_citation_count?: number;
    reference_count?: number;
    tldr?: string;
    source: 'arxiv' | 'semantic_scholar';
}

export interface LiteratureSearchResult {
    papers: PaperMetadata[];
    total: number;
    query: string;
}

export type LiteratureSource = 'arxiv' | 'semantic_scholar';

export interface LiteratureSearchOptions {
    query: string;
    sources?: LiteratureSource[];
    limit?: number;
}
