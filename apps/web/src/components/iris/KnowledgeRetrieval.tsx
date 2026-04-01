'use client';

import { useState } from 'react';
import type { IrisKnowledgeSection } from '@/types/iris';
import { Search, BookOpen, Loader2, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';

interface KnowledgeRetrievalProps {
    idea: string;
    onImproveWithKnowledge: () => void;
    isLoading: boolean;
}

export default function KnowledgeRetrieval({ idea, onImproveWithKnowledge, isLoading }: KnowledgeRetrievalProps) {
    const [query, setQuery] = useState('');
    const [sections, setSections] = useState<IrisKnowledgeSection[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [isGeneratingQuery, setIsGeneratingQuery] = useState(false);
    const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleGenerateQuery = async () => {
        if (!idea) return;
        setIsGeneratingQuery(true);
        setError(null);
        try {
            const res = await fetch('/api/iris/generate-query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            setQuery(data.query || '');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to generate query');
        } finally {
            setIsGeneratingQuery(false);
        }
    };

    const handleSearch = async () => {
        if (!query.trim()) return;
        setIsSearching(true);
        setError(null);
        setSections([]);
        try {
            const res = await fetch('/api/iris/retrieve-knowledge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            setSections(data.sections || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Search failed');
        } finally {
            setIsSearching(false);
        }
    };

    return (
        <div style={{
            background: 'var(--bg-elevated, #12121f)',
            border: '1px solid var(--border-subtle, #1e1e35)',
            borderRadius: 'var(--radius-lg, 12px)',
            overflow: 'hidden',
        }}>
            <div style={{
                padding: '10px 16px',
                borderBottom: '1px solid var(--border-subtle, #1e1e35)',
                fontSize: 13, fontWeight: 600,
                color: 'var(--text-primary, #e8eaf0)',
                display: 'flex', alignItems: 'center', gap: 6,
            }}>
                <BookOpen size={14} />
                Literature Retrieval
            </div>

            <div style={{ padding: 16 }}>
                {/* Query input */}
                <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                        placeholder="Enter search query..."
                        style={{
                            flex: 1, padding: '6px 10px', borderRadius: 'var(--radius-sm, 6px)',
                            border: '1px solid var(--border-subtle, #1e1e35)',
                            background: 'var(--bg-surface, #0d0d18)',
                            color: 'var(--text-primary)', fontSize: 12,
                            outline: 'none',
                        }}
                    />
                    <button
                        onClick={handleGenerateQuery}
                        disabled={isGeneratingQuery || !idea}
                        style={{
                            padding: '6px 10px', borderRadius: 'var(--radius-sm, 6px)',
                            border: '1px solid var(--border-subtle)',
                            background: 'var(--bg-surface)', cursor: 'pointer',
                            color: 'var(--accent-indigo-light, #818cf8)', fontSize: 11,
                            display: 'flex', alignItems: 'center', gap: 4,
                        }}
                        title="Auto-generate query from current idea"
                    >
                        {isGeneratingQuery ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                    </button>
                    <button
                        onClick={handleSearch}
                        disabled={isSearching || !query.trim()}
                        style={{
                            padding: '6px 10px', borderRadius: 'var(--radius-sm, 6px)',
                            border: 'none', background: 'var(--accent-indigo, #6366f1)',
                            color: '#fff', cursor: 'pointer', fontSize: 11,
                            display: 'flex', alignItems: 'center', gap: 4,
                        }}
                    >
                        {isSearching ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
                        Search
                    </button>
                </div>

                {error && (
                    <div style={{ fontSize: 11, color: '#f87171', marginBottom: 8 }}>{error}</div>
                )}

                {/* Results */}
                {sections.length > 0 && (
                    <div style={{ maxHeight: 300, overflow: 'auto' }}>
                        {sections.map((section, idx) => (
                            <div
                                key={idx}
                                style={{
                                    marginBottom: 6, borderRadius: 'var(--radius-sm, 6px)',
                                    border: '1px solid var(--border-subtle, #1e1e35)',
                                    overflow: 'hidden',
                                }}
                            >
                                <button
                                    onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                                    style={{
                                        width: '100%', textAlign: 'left',
                                        padding: '8px 12px',
                                        background: 'var(--bg-surface, #0d0d18)',
                                        border: 'none', cursor: 'pointer',
                                        color: 'var(--text-primary)', fontSize: 12,
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    }}
                                >
                                    <span style={{ fontWeight: 500 }}>{section.title || `Section ${idx + 1}`}</span>
                                    {expandedIdx === idx ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                                </button>
                                {expandedIdx === idx && (
                                    <div style={{ padding: '8px 12px', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                                        <p>{section.summary}</p>
                                        {section.citations && section.citations.length > 0 && (
                                            <div style={{ marginTop: 8 }}>
                                                <div style={{ fontSize: 10, fontWeight: 600, marginBottom: 4 }}>Citations:</div>
                                                {section.citations.map((c, ci) => (
                                                    <div key={ci} style={{ fontSize: 10, marginBottom: 2 }}>
                                                        {c.url ? (
                                                            <a href={c.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo-light)' }}>
                                                                {c.title}
                                                            </a>
                                                        ) : (
                                                            <span>{c.title}</span>
                                                        )}
                                                        {c.year && <span> ({c.year})</span>}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}

                        <button
                            onClick={onImproveWithKnowledge}
                            disabled={isLoading}
                            style={{
                                width: '100%', marginTop: 8, padding: '8px 16px',
                                borderRadius: 'var(--radius-sm, 6px)',
                                border: 'none', background: 'var(--accent-indigo, #6366f1)',
                                color: '#fff', fontSize: 12, fontWeight: 600,
                                cursor: isLoading ? 'wait' : 'pointer',
                                opacity: isLoading ? 0.6 : 1,
                            }}
                        >
                            {isLoading ? 'Improving...' : 'Improve Idea with Knowledge'}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
