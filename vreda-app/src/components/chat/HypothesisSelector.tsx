'use client';

import { useState } from 'react';
import type { Hypothesis, BrainstormerOutput } from '@/types/strategist';
import {
    Maximize2,
    Shuffle,
    Scissors,
    CheckCircle,
    Send,
    BookOpen,
    Sparkles,
    FlaskConical,
    ChevronDown,
    ChevronRight,
} from 'lucide-react';

interface HypothesisSelectorProps {
    brainstormerOutput: BrainstormerOutput;
    onSelect: (hypothesisId: string) => void;
    onRefine: (message: string) => void;
    disabled?: boolean;
}

const typeConfig: Record<Hypothesis['type'], { icon: typeof Maximize2; label: string; color: string }> = {
    scale: {
        icon: Maximize2,
        label: 'Scale',
        color: 'var(--accent-indigo-light)',
    },
    modality_shift: {
        icon: Shuffle,
        label: 'Modality Shift',
        color: 'var(--accent-cyan)',
    },
    architecture_ablation: {
        icon: Scissors,
        label: 'Architecture Ablation',
        color: 'var(--accent-amber)',
    },
};

export default function HypothesisSelector({
    brainstormerOutput,
    onSelect,
    onRefine,
    disabled = false,
}: HypothesisSelectorProps) {
    const [refinementText, setRefinementText] = useState('');
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [expandedEvidence, setExpandedEvidence] = useState<Set<string>>(new Set());

    const handleSelect = (id: string) => {
        setSelectedId(id);
        onSelect(id);
    };

    const handleRefine = () => {
        if (!refinementText.trim()) return;
        onRefine(refinementText.trim());
        setRefinementText('');
    };

    return (
        <div className="manifest-card">
            <div className="manifest-header">
                <CheckCircle size={18} />
                <h3>Hypothesis Options</h3>
            </div>

            {/* Reasoning Context */}
            {brainstormerOutput.reasoning_context && (
                <div className="manifest-section">
                    <p style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                        {brainstormerOutput.reasoning_context}
                    </p>
                </div>
            )}

            {/* Hypothesis Cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
                {brainstormerOutput.hypotheses.map((h) => {
                    const config = typeConfig[h.type];
                    const Icon = config.icon;
                    const isSelected = selectedId === h.id;

                    return (
                        <div
                            key={h.id}
                            style={{
                                background: isSelected
                                    ? 'rgba(99, 102, 241, 0.08)'
                                    : 'var(--bg-surface)',
                                border: isSelected
                                    ? '1px solid var(--accent-indigo)'
                                    : '1px solid var(--border-subtle)',
                                borderRadius: 'var(--radius-md)',
                                padding: '14px 16px',
                                cursor: disabled ? 'default' : 'pointer',
                                transition: 'all 0.2s',
                                opacity: disabled ? 0.7 : 1,
                            }}
                            onClick={() => !disabled && handleSelect(h.id)}
                        >
                            {/* Header row */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                                <Icon size={14} color={config.color} />
                                <span
                                    className="manifest-tag"
                                    style={{
                                        background: `${config.color}20`,
                                        color: config.color,
                                        border: `1px solid ${config.color}33`,
                                        fontSize: 10,
                                    }}
                                >
                                    {config.label}
                                </span>
                                <span
                                    className="manifest-tag"
                                    style={{
                                        marginLeft: 'auto',
                                        background: 'var(--bg-primary)',
                                        color: 'var(--text-muted)',
                                        fontSize: 10,
                                    }}
                                >
                                    {h.estimated_complexity.toUpperCase()}
                                </span>
                            </div>

                            {/* Title & Description */}
                            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', marginBottom: 4 }}>
                                {h.title}
                            </div>
                            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 8 }}>
                                {h.description}
                            </p>

                            {/* Prediction */}
                            <div
                                style={{
                                    fontSize: 12,
                                    color: 'var(--accent-cyan)',
                                    background: 'var(--accent-cyan-glow)',
                                    padding: '6px 10px',
                                    borderRadius: 'var(--radius-sm)',
                                    marginBottom: 8,
                                }}
                            >
                                Prediction: {h.testable_prediction}
                            </div>

                            {/* Scores bar */}
                            <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-muted)' }}>
                                <span>
                                    Feasibility:{' '}
                                    <strong style={{ color: scoreColor(h.feasibility_score) }}>
                                        {h.feasibility_score}%
                                    </strong>
                                </span>
                                <span>
                                    Confidence:{' '}
                                    <strong style={{ color: scoreColor(h.confidence) }}>
                                        {h.confidence}%
                                    </strong>
                                </span>
                            </div>

                            {/* Feasibility bar */}
                            <div style={{ marginTop: 6 }}>
                                <div className="progress-bar" style={{ height: 3 }}>
                                    <div
                                        className="progress-bar-fill"
                                        style={{
                                            width: `${h.feasibility_score}%`,
                                            animation: 'none',
                                            background: scoreColor(h.feasibility_score),
                                        }}
                                    />
                                </div>
                            </div>

                            {/* Evidence & Novelty toggle (only if data exists) */}
                            {(h.evidence_basis || h.novelty_assessment || h.experiment_design) && (
                                <>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setExpandedEvidence(prev => {
                                                const next = new Set(prev);
                                                if (next.has(h.id)) next.delete(h.id);
                                                else next.add(h.id);
                                                return next;
                                            });
                                        }}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 4,
                                            marginTop: 8,
                                            padding: '4px 0',
                                            background: 'none',
                                            border: 'none',
                                            color: 'var(--accent-indigo-light)',
                                            cursor: 'pointer',
                                            fontSize: 11,
                                            fontFamily: 'inherit',
                                        }}
                                    >
                                        {expandedEvidence.has(h.id) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                        Evidence &amp; Experiment Design
                                        {h.novelty_assessment && (
                                            <span
                                                className="manifest-tag"
                                                style={{
                                                    marginLeft: 6,
                                                    fontSize: 9,
                                                    background: h.novelty_assessment.is_novel
                                                        ? 'rgba(16,185,129,0.12)'
                                                        : 'rgba(245,158,11,0.12)',
                                                    color: h.novelty_assessment.is_novel
                                                        ? 'var(--accent-green)'
                                                        : 'var(--accent-amber)',
                                                    border: 'none',
                                                }}
                                            >
                                                {h.novelty_assessment.is_novel ? 'Novel' : 'Has Prior Work'}
                                            </span>
                                        )}
                                    </button>

                                    {expandedEvidence.has(h.id) && (
                                        <div style={{ marginTop: 4 }}>
                                            {/* Evidence Basis */}
                                            {h.evidence_basis && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <BookOpen size={10} /> Evidence Basis
                                                    </div>
                                                    <div className="hyp-evidence-insight">{h.evidence_basis.key_insight}</div>
                                                    {h.evidence_basis.supporting_papers.length > 0 && (
                                                        <div className="hyp-evidence-papers">
                                                            {h.evidence_basis.supporting_papers.slice(0, 3).map((p, i) => (
                                                                <div key={i} className="hyp-evidence-paper">
                                                                    <span className="hyp-evidence-paper-title">{p.title}</span>
                                                                    <span className="hyp-evidence-paper-meta">
                                                                        {p.year || '?'} &middot; {p.citation_count} citations
                                                                    </span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                    {h.evidence_basis.prior_results && (
                                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                                                            Prior: {h.evidence_basis.prior_results}
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Novelty Assessment */}
                                            {h.novelty_assessment && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <Sparkles size={10} /> Novelty ({h.novelty_assessment.novelty_score}/100)
                                                    </div>
                                                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                                        {h.novelty_assessment.what_is_new}
                                                    </div>
                                                    {h.novelty_assessment.similar_work.length > 0 && (
                                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                                                            Similar: {h.novelty_assessment.similar_work.join(', ')}
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Experiment Design */}
                                            {h.experiment_design && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <FlaskConical size={10} /> Experiment Design
                                                    </div>
                                                    <div className="hyp-experiment-grid">
                                                        <div className="hyp-experiment-item">
                                                            <span className="hyp-experiment-key">Baseline</span>
                                                            <span className="hyp-experiment-val">{h.experiment_design.baseline.description}</span>
                                                        </div>
                                                        <div className="hyp-experiment-item">
                                                            <span className="hyp-experiment-key">IV</span>
                                                            <span className="hyp-experiment-val">{h.experiment_design.independent_variable}</span>
                                                        </div>
                                                        {h.experiment_design.success_metrics.slice(0, 2).map((m, i) => (
                                                            <div key={i} className="hyp-experiment-item">
                                                                <span className="hyp-experiment-key">{m.metric_name}</span>
                                                                <span className="hyp-experiment-val">{m.target_value}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                    {h.experiment_design.dataset_requirements.length > 0 && (
                                                        <div className="paper-card-chip-row" style={{ marginTop: 4 }}>
                                                            {h.experiment_design.dataset_requirements.map((d, i) => (
                                                                <span key={i} className="paper-card-chip chip-cyan" style={{ fontSize: 10 }}>
                                                                    {d.name}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Refinement Input */}
            <div className="manifest-section" style={{ marginBottom: 0 }}>
                <div className="manifest-section-title">Refine Hypotheses</div>
                <div
                    style={{
                        display: 'flex',
                        gap: 8,
                        alignItems: 'flex-end',
                    }}
                >
                    <textarea
                        value={refinementText}
                        onChange={(e) => setRefinementText(e.target.value)}
                        placeholder="Ask for different hypotheses or adjust these..."
                        disabled={disabled}
                        style={{
                            flex: 1,
                            background: 'var(--bg-surface)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--radius-sm)',
                            color: 'var(--text-primary)',
                            fontSize: 13,
                            padding: '8px 12px',
                            resize: 'none',
                            height: 40,
                            outline: 'none',
                            fontFamily: 'inherit',
                        }}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleRefine();
                            }
                        }}
                    />
                    <button
                        onClick={handleRefine}
                        disabled={disabled || !refinementText.trim()}
                        style={{
                            background: 'var(--accent-indigo)',
                            border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            color: 'white',
                            width: 36,
                            height: 36,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: disabled ? 'not-allowed' : 'pointer',
                            opacity: disabled || !refinementText.trim() ? 0.5 : 1,
                            flexShrink: 0,
                        }}
                    >
                        <Send size={14} />
                    </button>
                </div>
            </div>
        </div>
    );
}

function scoreColor(score: number): string {
    if (score >= 70) return 'var(--accent-green)';
    if (score >= 40) return 'var(--accent-amber)';
    return 'var(--accent-red)';
}
