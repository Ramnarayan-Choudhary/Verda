'use client';

import { BookOpen, ExternalLink, Download, Users, Quote } from 'lucide-react';
import type { PaperMetadata } from '@/lib/literature/types';

interface PaperSearchCardProps {
    papers: PaperMetadata[];
    query: string;
    onImport: (paper: PaperMetadata) => void;
    importing?: string | null; // arxiv_id or title of paper being imported
}

export default function PaperSearchCard({
    papers,
    query,
    onImport,
    importing,
}: PaperSearchCardProps) {
    if (!papers.length) {
        return (
            <div className="paper-search-card paper-search-empty">
                <BookOpen size={20} />
                <p>No papers found for &quot;{query}&quot;</p>
            </div>
        );
    }

    return (
        <div className="paper-search-card">
            <div className="paper-search-header">
                <BookOpen size={16} />
                <span>{papers.length} papers found for &quot;{query}&quot;</span>
            </div>

            <div className="paper-search-list">
                {papers.map((paper, idx) => {
                    const key = paper.arxiv_id || paper.semantic_scholar_id || idx;
                    const isImporting = importing === (paper.arxiv_id || paper.title);
                    const year = paper.published?.slice(0, 4) || '';

                    return (
                        <div key={key} className="paper-search-item">
                            <div className="paper-search-item-header">
                                <h4 className="paper-search-title">{paper.title}</h4>
                                {paper.pdf_url && (
                                    <a
                                        href={paper.pdf_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="paper-search-pdf-link"
                                        title="Open PDF"
                                    >
                                        <ExternalLink size={12} />
                                    </a>
                                )}
                            </div>

                            <div className="paper-search-meta">
                                {paper.authors.length > 0 && (
                                    <span className="paper-search-authors">
                                        <Users size={11} />
                                        {paper.authors.slice(0, 3).join(', ')}
                                        {paper.authors.length > 3 && ` +${paper.authors.length - 3}`}
                                    </span>
                                )}
                                {year && <span className="paper-search-year">{year}</span>}
                                {paper.citation_count !== undefined && paper.citation_count > 0 && (
                                    <span className="paper-search-citations">
                                        <Quote size={11} />
                                        {paper.citation_count.toLocaleString()}
                                        {paper.influential_citation_count !== undefined && paper.influential_citation_count > 0 && (
                                            <span className="paper-search-influential" title="Influential citations">
                                                ({paper.influential_citation_count} influential)
                                            </span>
                                        )}
                                    </span>
                                )}
                                {paper.arxiv_id && (
                                    <span className="paper-search-arxiv-badge">
                                        arXiv:{paper.arxiv_id}
                                    </span>
                                )}
                            </div>

                            {paper.tldr && (
                                <p className="paper-search-tldr">{paper.tldr}</p>
                            )}

                            {!paper.tldr && paper.abstract && (
                                <p className="paper-search-abstract">
                                    {paper.abstract.length > 200
                                        ? paper.abstract.slice(0, 200) + '...'
                                        : paper.abstract}
                                </p>
                            )}

                            {paper.categories.length > 0 && (
                                <div className="paper-search-categories">
                                    {paper.categories.slice(0, 4).map(cat => (
                                        <span key={cat} className="paper-search-cat-tag">{cat}</span>
                                    ))}
                                </div>
                            )}

                            {paper.arxiv_id && (
                                <button
                                    className="paper-search-import-btn"
                                    onClick={() => onImport(paper)}
                                    disabled={!!importing}
                                >
                                    {isImporting ? (
                                        <>
                                            <div className="spinner-small" />
                                            Importing...
                                        </>
                                    ) : (
                                        <>
                                            <Download size={13} />
                                            Import to VREDA
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
