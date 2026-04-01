'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { IrisReviewScores } from '@/types/iris';
import { RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

interface IdeaPanelProps {
    idea: string;
    reviewScores: IrisReviewScores;
    averageScore: number;
    onRefreshIdea: () => void;
    isLoading: boolean;
}

function ScoreBar({ label, score }: { label: string; score: number }) {
    const pct = (score / 10) * 100;
    const color =
        score >= 7 ? 'var(--accent-green, #4ade80)' :
        score >= 5 ? 'var(--accent-amber, #fbbf24)' :
        'var(--accent-red, #f87171)';

    return (
        <div style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                <span style={{ color: 'var(--text-secondary, #8b8fa3)', textTransform: 'capitalize' }}>{label}</span>
                <span style={{ color, fontWeight: 600 }}>{score.toFixed(1)}</span>
            </div>
            <div style={{ height: 4, borderRadius: 2, background: 'var(--bg-surface, #1a1a2e)' }}>
                <div style={{ height: '100%', width: `${pct}%`, borderRadius: 2, background: color, transition: 'width 0.5s ease' }} />
            </div>
        </div>
    );
}

export default function IdeaPanel({ idea, reviewScores, averageScore, onRefreshIdea, isLoading }: IdeaPanelProps) {
    const [collapsed, setCollapsed] = useState(false);
    const hasScores = Object.keys(reviewScores).length > 0;

    return (
        <div style={{
            background: 'var(--bg-elevated, #12121f)',
            border: '1px solid var(--border-subtle, #1e1e35)',
            borderRadius: 'var(--radius-lg, 12px)',
            overflow: 'hidden',
        }}>
            {/* Header */}
            <div
                style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 16px',
                    borderBottom: collapsed ? 'none' : '1px solid var(--border-subtle, #1e1e35)',
                    cursor: 'pointer',
                }}
                onClick={() => setCollapsed(!collapsed)}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary, #e8eaf0)' }}>
                        Research Idea
                    </span>
                    {hasScores && (
                        <span style={{
                            fontSize: 11, padding: '2px 8px',
                            borderRadius: 'var(--radius-sm, 6px)',
                            background: averageScore >= 7
                                ? 'rgba(74,222,128,0.12)' : averageScore >= 5
                                ? 'rgba(251,191,36,0.12)' : 'rgba(248,113,113,0.12)',
                            color: averageScore >= 7
                                ? '#4ade80' : averageScore >= 5
                                ? '#fbbf24' : '#f87171',
                            fontWeight: 600,
                        }}>
                            {averageScore.toFixed(1)}/10
                        </span>
                    )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <button
                        onClick={(e) => { e.stopPropagation(); onRefreshIdea(); }}
                        disabled={isLoading}
                        style={{
                            background: 'none', border: 'none', cursor: isLoading ? 'wait' : 'pointer',
                            color: 'var(--text-secondary, #8b8fa3)', padding: 4,
                        }}
                        title="Generate new approach"
                    >
                        <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
                    </button>
                    {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                </div>
            </div>

            {!collapsed && (
                <div style={{ padding: 16 }}>
                    {/* Idea Content */}
                    <div style={{
                        maxHeight: 400, overflow: 'auto',
                        fontSize: 13, lineHeight: 1.7,
                        color: 'var(--text-primary, #e8eaf0)',
                    }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{idea || '_No idea generated yet._'}</ReactMarkdown>
                    </div>

                    {/* Review Scores */}
                    {hasScores && (
                        <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-subtle, #1e1e35)' }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10 }}>
                                Review Scores
                            </div>
                            {Object.entries(reviewScores).map(([key, val]) => (
                                <ScoreBar key={key} label={key} score={val ?? 0} />
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
