'use client';

import { useState } from 'react';
import { IRIS_REVIEW_ASPECTS } from '@/types/iris';
import type { IrisReviewAspectData } from '@/types/iris';
import { Search, Check, X, Loader2, ChevronRight } from 'lucide-react';

interface ReviewPanelProps {
    idea: string;
    onImproveIdea: (acceptedReviews: IrisReviewAspectData[]) => void;
    isLoading: boolean;
}

const ASPECT_LABELS: Record<string, string> = {
    lack_of_novelty: 'Novelty',
    assumptions: 'Assumptions',
    vagueness: 'Vagueness',
    feasibility_and_practicality: 'Feasibility',
    overgeneralization: 'Overgeneralization',
    overstatement: 'Overstatement',
    evaluation_and_validation_issues: 'Evaluation',
    justification_for_methods: 'Methods',
    reproducibility: 'Reproducibility',
    contradictory_statements: 'Contradictions',
    impact: 'Impact',
    alignment: 'Alignment',
    ethical_and_social_considerations: 'Ethics',
    robustness: 'Robustness',
};

export default function ReviewPanel({ idea, onImproveIdea, isLoading }: ReviewPanelProps) {
    const [reviews, setReviews] = useState<Map<string, IrisReviewAspectData>>(new Map());
    const [acceptedAspects, setAcceptedAspects] = useState<Set<string>>(new Set());
    const [reviewingAspect, setReviewingAspect] = useState<string | null>(null);
    const [isReviewing, setIsReviewing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleReviewAspect = async (aspect: string) => {
        if (isReviewing || !idea) return;
        setIsReviewing(true);
        setReviewingAspect(aspect);
        setError(null);

        try {
            const res = await fetch('/api/iris/review-aspect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea, aspect }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);

            const reviewData: IrisReviewAspectData = data.review_data;
            setReviews((prev) => new Map(prev).set(aspect, reviewData));
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Review failed');
        } finally {
            setIsReviewing(false);
            setReviewingAspect(null);
        }
    };

    const handleReviewAll = async () => {
        setIsReviewing(true);
        setError(null);
        for (const aspect of IRIS_REVIEW_ASPECTS) {
            if (reviews.has(aspect)) continue;
            setReviewingAspect(aspect);
            try {
                const res = await fetch('/api/iris/review-aspect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ idea, aspect }),
                });
                const data = await res.json();
                if (res.ok && data.review_data) {
                    setReviews((prev) => new Map(prev).set(aspect, data.review_data));
                }
            } catch {
                // Continue with remaining aspects
            }
        }
        setIsReviewing(false);
        setReviewingAspect(null);
    };

    const toggleAccept = (aspect: string) => {
        setAcceptedAspects((prev) => {
            const next = new Set(prev);
            if (next.has(aspect)) next.delete(aspect);
            else next.add(aspect);
            return next;
        });
    };

    const handleImprove = () => {
        const accepted = Array.from(acceptedAspects)
            .map((a) => reviews.get(a))
            .filter(Boolean) as IrisReviewAspectData[];
        if (accepted.length > 0) {
            onImproveIdea(accepted);
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
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 16px',
                borderBottom: '1px solid var(--border-subtle, #1e1e35)',
            }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary, #e8eaf0)' }}>
                    Detailed Review ({reviews.size}/{IRIS_REVIEW_ASPECTS.length})
                </span>
                <button
                    onClick={handleReviewAll}
                    disabled={isReviewing || !idea}
                    style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        padding: '4px 10px', borderRadius: 'var(--radius-sm, 6px)',
                        border: '1px solid var(--border-subtle, #1e1e35)',
                        background: 'var(--bg-surface, #0d0d18)',
                        color: 'var(--accent-indigo-light, #818cf8)',
                        fontSize: 11, cursor: isReviewing ? 'wait' : 'pointer',
                        opacity: isReviewing ? 0.6 : 1,
                    }}
                >
                    {isReviewing ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
                    Review All
                </button>
            </div>

            <div style={{ maxHeight: 400, overflow: 'auto' }}>
                {IRIS_REVIEW_ASPECTS.map((aspect) => {
                    const review = reviews.get(aspect);
                    const isActive = reviewingAspect === aspect;
                    const isAccepted = acceptedAspects.has(aspect);

                    return (
                        <div
                            key={aspect}
                            style={{
                                padding: '8px 16px',
                                borderBottom: '1px solid var(--border-subtle, #1e1e35)',
                                background: isAccepted ? 'rgba(74,222,128,0.04)' : 'transparent',
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <button
                                    onClick={() => handleReviewAspect(aspect)}
                                    disabled={isReviewing}
                                    style={{
                                        display: 'flex', alignItems: 'center', gap: 6,
                                        background: 'none', border: 'none',
                                        color: 'var(--text-primary, #e8eaf0)',
                                        fontSize: 12, cursor: 'pointer', padding: 0,
                                    }}
                                >
                                    {isActive ? <Loader2 size={12} className="animate-spin" /> : <ChevronRight size={12} />}
                                    {ASPECT_LABELS[aspect] || aspect}
                                    {review && (
                                        <span style={{
                                            fontSize: 10, padding: '1px 5px',
                                            borderRadius: 4,
                                            background: (review.score ?? 0) >= 7 ? 'rgba(74,222,128,0.15)' : 'rgba(251,191,36,0.15)',
                                            color: (review.score ?? 0) >= 7 ? '#4ade80' : '#fbbf24',
                                        }}>
                                            {review.score}/10
                                        </span>
                                    )}
                                </button>
                                {review && (
                                    <div style={{ display: 'flex', gap: 4 }}>
                                        <button
                                            onClick={() => toggleAccept(aspect)}
                                            style={{
                                                background: isAccepted ? 'rgba(74,222,128,0.15)' : 'none',
                                                border: '1px solid',
                                                borderColor: isAccepted ? '#4ade80' : 'var(--border-subtle)',
                                                borderRadius: 4, padding: 2, cursor: 'pointer',
                                                color: isAccepted ? '#4ade80' : 'var(--text-secondary)',
                                            }}
                                            title={isAccepted ? 'Accepted — click to undo' : 'Accept this feedback'}
                                        >
                                            <Check size={12} />
                                        </button>
                                        <button
                                            onClick={() => {
                                                setAcceptedAspects((p) => { const n = new Set(p); n.delete(aspect); return n; });
                                            }}
                                            style={{
                                                background: 'none', border: '1px solid var(--border-subtle)',
                                                borderRadius: 4, padding: 2, cursor: 'pointer',
                                                color: 'var(--text-secondary)',
                                            }}
                                            title="Ignore this feedback"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                )}
                            </div>
                            {review && (
                                <div style={{
                                    marginTop: 6, fontSize: 11,
                                    color: 'var(--text-secondary, #8b8fa3)',
                                    lineHeight: 1.5,
                                }}>
                                    {review.summary || review.feedback || 'No detailed feedback.'}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {error && (
                <div style={{ padding: '8px 16px', fontSize: 11, color: '#f87171' }}>
                    {error}
                </div>
            )}

            {acceptedAspects.size > 0 && (
                <div style={{
                    padding: '10px 16px',
                    borderTop: '1px solid var(--border-subtle, #1e1e35)',
                }}>
                    <button
                        onClick={handleImprove}
                        disabled={isLoading}
                        style={{
                            width: '100%', padding: '8px 16px',
                            borderRadius: 'var(--radius-sm, 6px)',
                            border: 'none',
                            background: 'var(--accent-indigo, #6366f1)',
                            color: '#fff', fontSize: 12, fontWeight: 600,
                            cursor: isLoading ? 'wait' : 'pointer',
                            opacity: isLoading ? 0.6 : 1,
                        }}
                    >
                        {isLoading ? 'Improving...' : `Improve Idea (${acceptedAspects.size} suggestions)`}
                    </button>
                </div>
            )}
        </div>
    );
}
