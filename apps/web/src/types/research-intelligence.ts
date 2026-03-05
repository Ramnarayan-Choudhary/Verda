// ============================================
// VREDA.ai Research Intelligence Type Definitions
// ============================================

// ---- Code Discovery (Papers With Code + GitHub) ----

export interface RepoMetrics {
    url: string;
    owner: string;
    name: string;
    stars: number;
    forks: number;
    open_issues: number;
    last_pushed: string;
    primary_language: string;
    languages: Record<string, number>;
    framework: string | null;
    has_readme: boolean;
    readme_preview: string;
    days_since_last_push: number;
    health_score: number;
}

export interface PapersWithCodeResult {
    paper_id: string;
    paper_title: string;
    repositories: {
        url: string;
        stars: number;
        framework: string | null;
        description: string;
        is_official: boolean;
    }[];
    tasks: string[];
    methods: string[];
}

export interface CodeDiscovery {
    papers_with_code: PapersWithCodeResult | null;
    repos: RepoMetrics[];
    best_repo: RepoMetrics | null;
    total_repos_found: number;
    source: 'papers_with_code' | 'github_search' | 'paper_urls' | 'none';
}

// ---- Citation Graph (Semantic Scholar) ----

export interface CitationPaper {
    semantic_scholar_id: string;
    title: string;
    year: number | null;
    citation_count: number;
    arxiv_id: string | null;
    venue: string | null;
    influential: boolean;
    fields_of_study: string[];
}

export interface CitationGraph {
    references: CitationPaper[];
    citations: CitationPaper[];
    influential_citation_count: number;
    total_citation_count: number;
    reference_count: number;
    highly_cited_references: CitationPaper[];
    recent_citations: CitationPaper[];
}

// ---- Related Work Discovery ----

export interface RelatedPaper {
    title: string;
    arxiv_id: string | null;
    semantic_scholar_id: string;
    year: number | null;
    citation_count: number;
    abstract: string;
    venue: string | null;
    relevance_source: 'recommendation' | 'keyword_search' | 'shared_references';
}

export interface RelatedWork {
    papers: RelatedPaper[];
    research_landscape_size: number;
}

// ---- Aggregated Intelligence ----

export interface ResearchIntelligence {
    code_discovery: CodeDiscovery;
    citation_graph: CitationGraph;
    related_work: RelatedWork;

    paper_arxiv_id: string | null;
    paper_s2_id: string | null;
    paper_title: string;
    gathered_at: string;
    latency_ms: number;

    errors: {
        source: 'papers_with_code' | 'github' | 'semantic_scholar_citations' | 'semantic_scholar_related' | 'semantic_scholar_recommendations';
        message: string;
    }[];
}

// ---- Experiment Design (for enhanced Brainstormer) ----

export interface ExperimentDesign {
    baseline: {
        description: string;
        source: string;
        expected_value: string;
    };
    success_metrics: {
        metric_name: string;
        target_value: string;
        measurement_method: string;
    }[];
    dataset_requirements: {
        name: string;
        size: string;
        availability: 'public' | 'requires_download' | 'requires_generation';
        source_url?: string;
    }[];
    control_variables: string[];
    independent_variable: string;
    dependent_variables: string[];
}
