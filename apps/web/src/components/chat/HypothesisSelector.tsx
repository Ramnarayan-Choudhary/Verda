'use client';

import { useState } from 'react';
import type { BrainstormerOutput, GeneratorOutput, EnhancedHypothesis, DimensionScores } from '@/types/strategist';
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
    ShieldCheck,
    AlertTriangle,
    Zap,
    Globe,
    Database,
    Brain,
    Lightbulb,
    Layers,
    GitMerge,
    Unlock,
    Trophy,
    BarChart3,
} from 'lucide-react';

// ---- Types ----

interface HypothesisSelectorProps {
    brainstormerOutput: BrainstormerOutput;
    pipelineOutput?: GeneratorOutput | null;
    onSelect: (hypothesisId: string) => void;
    onRefine: (message: string, hypothesisEngine: 'gpt' | 'claude') => void;
    disabled?: boolean;
}

// ---- Type Config (all 10 hypothesis types) ----

const typeConfig: Record<string, { icon: typeof Maximize2; label: string; color: string }> = {
    scale: { icon: Maximize2, label: 'Scale', color: 'var(--accent-indigo-light)' },
    modality_shift: { icon: Shuffle, label: 'Modality Shift', color: 'var(--accent-cyan)' },
    architecture_ablation: { icon: Scissors, label: 'Architecture', color: 'var(--accent-amber)' },
    cross_domain_transfer: { icon: Globe, label: 'Cross-Domain', color: '#a78bfa' },
    efficiency_optimization: { icon: Zap, label: 'Efficiency', color: '#34d399' },
    failure_mode_analysis: { icon: AlertTriangle, label: 'Failure Mode', color: '#f87171' },
    data_augmentation: { icon: Database, label: 'Data Aug.', color: '#60a5fa' },
    theoretical_extension: { icon: Brain, label: 'Theory', color: '#c084fc' },
    combination: { icon: GitMerge, label: 'Combination', color: '#fbbf24' },
    constraint_relaxation: { icon: Unlock, label: 'Relaxation', color: '#2dd4bf' },
};

const defaultTypeConfig = { icon: Lightbulb, label: 'Hypothesis', color: 'var(--accent-indigo-light)' };

// ---- Dimension display labels ----

const DIMENSION_LABELS: Record<keyof DimensionScores, { label: string; color: string }> = {
    novelty: { label: 'Novelty', color: '#a78bfa' },
    feasibility: { label: 'Feasibility', color: '#34d399' },
    impact: { label: 'Impact', color: '#f59e0b' },
    grounding: { label: 'Grounding', color: '#60a5fa' },
    testability: { label: 'Testability', color: '#f472b6' },
    clarity: { label: 'Clarity', color: '#2dd4bf' },
};

const NOVELTY_TYPE_LABELS: Record<string, string> = {
    entirely_new: 'Entirely New',
    new_combination: 'New Combination',
    new_application: 'New Application',
    incremental_extension: 'Incremental',
};

// ---- Component ----

export default function HypothesisSelector({
    brainstormerOutput,
    pipelineOutput,
    onSelect,
    onRefine,
    disabled = false,
}: HypothesisSelectorProps) {
    const [refinementText, setRefinementText] = useState('');
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [expandedEvidence, setExpandedEvidence] = useState<Set<string>>(new Set());
    const [selectedEngine, setSelectedEngine] = useState<'gpt' | 'claude'>(
        pipelineOutput?.engine_used === 'claude' ? 'claude' : 'gpt'
    );

    const handleSelect = (id: string) => {
        setSelectedId(id);
        onSelect(id);
    };

    const handleRefine = () => {
        if (!refinementText.trim()) return;
        onRefine(refinementText.trim(), selectedEngine);
        setRefinementText('');
    };

    // Use enhanced pipeline data when available
    const enhancedHypotheses = pipelineOutput?.hypotheses || null;
    const hasEnhancedData = !!enhancedHypotheses;

    // Build a lookup map for enhanced data
    const enhancedMap = new Map<string, EnhancedHypothesis>();
    if (enhancedHypotheses) {
        for (const h of enhancedHypotheses) {
            enhancedMap.set(h.id, h);
        }
    }

    return (
        <div className="manifest-card">
            <div className="manifest-header">
                <CheckCircle size={18} />
                <h3>Hypothesis Options</h3>
                {hasEnhancedData && pipelineOutput && (
                    <span
                        className="manifest-tag"
                        style={{
                            marginLeft: 'auto',
                            fontSize: 10,
                            background: 'rgba(99, 102, 241, 0.1)',
                            color: 'var(--accent-indigo-light)',
                            border: '1px solid rgba(99, 102, 241, 0.2)',
                        }}
                    >
                        {pipelineOutput.generation_strategy === 'knowledge_grounded' ? 'Knowledge-Grounded' : 'AI-Generated'}
                        {pipelineOutput.reflection_rounds > 0 && ` / ${pipelineOutput.reflection_rounds} reflections`}
                    </span>
                )}
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
                {brainstormerOutput.hypotheses.map((h, idx) => {
                    const config = typeConfig[h.type] || defaultTypeConfig;
                    const Icon = config.icon;
                    const isSelected = selectedId === h.id;
                    const enhanced = enhancedMap.get(h.id);

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
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                                {/* Rank badge */}
                                <span
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        width: 22,
                                        height: 22,
                                        borderRadius: '50%',
                                        background: idx === 0 ? 'var(--accent-indigo)' : 'var(--bg-primary)',
                                        color: idx === 0 ? 'white' : 'var(--text-muted)',
                                        fontSize: 11,
                                        fontWeight: 700,
                                        flexShrink: 0,
                                    }}
                                    title={idx === 0 ? 'Top Recommendation' : `Rank #${idx + 1}`}
                                >
                                    {idx === 0 ? <Trophy size={12} /> : idx + 1}
                                </span>

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

                                {h.critic_assessment && (
                                    <span
                                        className={`critic-badge critic-${h.critic_assessment.verdict}`}
                                        title={`Critic: ${h.critic_assessment.verdict}`}
                                    >
                                        <ShieldCheck size={10} />
                                        {h.critic_assessment.verdict}
                                    </span>
                                )}

                                {/* Novelty type badge */}
                                {enhanced?.novelty_assessment?.novelty_type && (
                                    <span
                                        className="manifest-tag"
                                        style={{
                                            fontSize: 9,
                                            background: enhanced.novelty_assessment.novelty_type === 'entirely_new'
                                                ? 'rgba(16,185,129,0.12)'
                                                : 'rgba(99,102,241,0.1)',
                                            color: enhanced.novelty_assessment.novelty_type === 'entirely_new'
                                                ? 'var(--accent-green)'
                                                : 'var(--accent-indigo-light)',
                                            border: 'none',
                                        }}
                                    >
                                        {NOVELTY_TYPE_LABELS[enhanced.novelty_assessment.novelty_type] || enhanced.novelty_assessment.novelty_type}
                                    </span>
                                )}

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

                            {/* Short hypothesis (one-liner from enhanced pipeline) */}
                            {enhanced?.short_hypothesis && (
                                <div style={{
                                    fontSize: 13,
                                    color: 'var(--text-primary)',
                                    fontStyle: 'italic',
                                    marginBottom: 6,
                                    lineHeight: 1.5,
                                }}>
                                    &ldquo;{enhanced.short_hypothesis}&rdquo;
                                </div>
                            )}

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

                            {/* Enhanced 6-dimension score bars */}
                            {enhanced?.scores ? (
                                <div style={{ marginBottom: 6 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                                        <BarChart3 size={12} color="var(--text-muted)" />
                                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                            Composite:{' '}
                                            <strong style={{ color: scoreColor(enhanced.composite_score) }}>
                                                {Math.round(enhanced.composite_score)}
                                            </strong>
                                            /100
                                        </span>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 12px' }}>
                                        {(Object.keys(DIMENSION_LABELS) as (keyof DimensionScores)[]).map((dim) => {
                                            const val = enhanced.scores[dim];
                                            const meta = DIMENSION_LABELS[dim];
                                            return (
                                                <div key={dim} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <span style={{ fontSize: 10, color: 'var(--text-muted)', width: 62, flexShrink: 0 }}>
                                                        {meta.label}
                                                    </span>
                                                    <div style={{
                                                        flex: 1,
                                                        height: 4,
                                                        background: 'var(--bg-primary)',
                                                        borderRadius: 2,
                                                        overflow: 'hidden',
                                                    }}>
                                                        <div style={{
                                                            width: `${val}%`,
                                                            height: '100%',
                                                            background: meta.color,
                                                            borderRadius: 2,
                                                            transition: 'width 0.3s',
                                                        }} />
                                                    </div>
                                                    <span style={{ fontSize: 10, color: scoreColor(val), fontWeight: 600, width: 24, textAlign: 'right' }}>
                                                        {val}
                                                    </span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            ) : (
                                /* Legacy scores fallback */
                                <>
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
                                        {h.critic_assessment && (
                                            <span>
                                                Grounding:{' '}
                                                <strong style={{ color: scoreColor(h.critic_assessment.grounding_score * 100) }}>
                                                    {Math.round(h.critic_assessment.grounding_score * 100)}%
                                                </strong>
                                            </span>
                                        )}
                                    </div>
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
                                </>
                            )}

                            {/* Risk factors */}
                            {enhanced?.risk_factors && enhanced.risk_factors.length > 0 && (
                                <div style={{
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    gap: 4,
                                    marginTop: 6,
                                }}>
                                    {enhanced.risk_factors.slice(0, 3).map((risk, i) => (
                                        <span
                                            key={i}
                                            className="manifest-tag"
                                            style={{
                                                fontSize: 9,
                                                background: 'rgba(248,113,113,0.08)',
                                                color: '#f87171',
                                                border: '1px solid rgba(248,113,113,0.15)',
                                                maxWidth: 200,
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap',
                                            }}
                                            title={risk}
                                        >
                                            <AlertTriangle size={8} style={{ marginRight: 3, flexShrink: 0 }} />
                                            {risk}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Evidence & Novelty toggle */}
                            {(h.evidence_basis || h.novelty_assessment || h.experiment_design || h.critic_assessment || enhanced) && (
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
                                        {(h.novelty_assessment || enhanced?.novelty_assessment) && (
                                            <span
                                                className="manifest-tag"
                                                style={{
                                                    marginLeft: 6,
                                                    fontSize: 9,
                                                    background: (h.novelty_assessment?.is_novel ?? enhanced?.novelty_assessment?.is_novel)
                                                        ? 'rgba(16,185,129,0.12)'
                                                        : 'rgba(245,158,11,0.12)',
                                                    color: (h.novelty_assessment?.is_novel ?? enhanced?.novelty_assessment?.is_novel)
                                                        ? 'var(--accent-green)'
                                                        : 'var(--accent-amber)',
                                                    border: 'none',
                                                }}
                                            >
                                                {(h.novelty_assessment?.is_novel ?? enhanced?.novelty_assessment?.is_novel) ? 'Novel' : 'Has Prior Work'}
                                            </span>
                                        )}
                                        {enhanced?.reflection_rounds_completed ? (
                                            <span
                                                className="manifest-tag"
                                                style={{ marginLeft: 4, fontSize: 9, background: 'rgba(99,102,241,0.08)', color: 'var(--accent-indigo-light)', border: 'none' }}
                                            >
                                                {enhanced.reflection_rounds_completed} reflection{enhanced.reflection_rounds_completed > 1 ? 's' : ''}
                                            </span>
                                        ) : null}
                                    </button>

                                    {expandedEvidence.has(h.id) && (
                                        <div style={{ marginTop: 4 }}>
                                            {/* Gap linkage */}
                                            {enhanced?.addresses_gap_id && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <Layers size={10} /> Addresses Research Gap
                                                    </div>
                                                    <div style={{ fontSize: 12, color: 'var(--accent-indigo-light)' }}>
                                                        {enhanced.addresses_gap_id}
                                                    </div>
                                                    {enhanced.evidence_basis?.gap_exploited && (
                                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                                                            {enhanced.evidence_basis.gap_exploited}
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Evidence Basis */}
                                            {(h.evidence_basis || enhanced?.evidence_basis) && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <BookOpen size={10} /> Evidence Basis
                                                    </div>
                                                    <div className="hyp-evidence-insight">
                                                        {h.evidence_basis?.key_insight || enhanced?.evidence_basis?.key_insight}
                                                    </div>
                                                    {((h.evidence_basis?.supporting_papers || enhanced?.evidence_basis?.supporting_papers) ?? []).length > 0 && (
                                                        <div className="hyp-evidence-papers">
                                                            {((h.evidence_basis?.supporting_papers || enhanced?.evidence_basis?.supporting_papers) ?? []).slice(0, 3).map((p, i) => (
                                                                <div key={i} className="hyp-evidence-paper">
                                                                    <span className="hyp-evidence-paper-title">{p.title}</span>
                                                                    <span className="hyp-evidence-paper-meta">
                                                                        {p.year || '?'} &middot; {p.citation_count} citations
                                                                    </span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                    {(h.evidence_basis?.prior_results || enhanced?.evidence_basis?.prior_results) && (
                                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                                                            Prior: {h.evidence_basis?.prior_results || enhanced?.evidence_basis?.prior_results}
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Novelty Assessment */}
                                            {(h.novelty_assessment || enhanced?.novelty_assessment) && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <Sparkles size={10} /> Novelty ({h.novelty_assessment?.novelty_score ?? enhanced?.novelty_assessment?.novelty_score}/100)
                                                    </div>
                                                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                                        {h.novelty_assessment?.what_is_new || enhanced?.novelty_assessment?.what_is_new}
                                                    </div>
                                                    {((h.novelty_assessment?.similar_work || enhanced?.novelty_assessment?.similar_work) ?? []).length > 0 && (
                                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                                                            Similar: {(h.novelty_assessment?.similar_work || enhanced?.novelty_assessment?.similar_work || []).join(', ')}
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Related Work Summary */}
                                            {enhanced?.related_work_summary && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <Globe size={10} /> Related Work
                                                    </div>
                                                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                                        {enhanced.related_work_summary}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Experiment Design */}
                                            {(h.experiment_design || enhanced?.experiment_design) && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <FlaskConical size={10} /> Experiment Design
                                                    </div>
                                                    {(() => {
                                                        const design = h.experiment_design || enhanced?.experiment_design;
                                                        if (!design) return null;
                                                        return (
                                                            <>
                                                                <div className="hyp-experiment-grid">
                                                                    <div className="hyp-experiment-item">
                                                                        <span className="hyp-experiment-key">Baseline</span>
                                                                        <span className="hyp-experiment-val">{design.baseline.description}</span>
                                                                    </div>
                                                                    <div className="hyp-experiment-item">
                                                                        <span className="hyp-experiment-key">IV</span>
                                                                        <span className="hyp-experiment-val">{design.independent_variable}</span>
                                                                    </div>
                                                                    {design.success_metrics.slice(0, 2).map((m, i) => (
                                                                        <div key={i} className="hyp-experiment-item">
                                                                            <span className="hyp-experiment-key">{m.metric_name}</span>
                                                                            <span className="hyp-experiment-val">{m.target_value}</span>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                                {design.dataset_requirements.length > 0 && (
                                                                    <div className="paper-card-chip-row" style={{ marginTop: 4 }}>
                                                                        {design.dataset_requirements.map((d, i) => (
                                                                            <span key={i} className="paper-card-chip chip-cyan" style={{ fontSize: 10 }}>
                                                                                {d.name}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                            </>
                                                        );
                                                    })()}
                                                </div>
                                            )}

                                            {/* Critic Notes */}
                                            {(h.critic_assessment || enhanced?.critic_assessment) && (
                                                <div className="hyp-evidence-section">
                                                    <div className="hyp-evidence-label">
                                                        <ShieldCheck size={10} /> Critic Notes
                                                        <span
                                                            className={`critic-badge critic-${(h.critic_assessment?.verdict || enhanced?.critic_assessment?.verdict)}`}
                                                            style={{ marginLeft: 6 }}
                                                        >
                                                            {h.critic_assessment?.verdict || enhanced?.critic_assessment?.verdict}
                                                        </span>
                                                    </div>
                                                    {(() => {
                                                        const critic = h.critic_assessment || enhanced?.critic_assessment;
                                                        if (!critic) return null;
                                                        return (
                                                            <>
                                                                {critic.feasibility_issues.length > 0 && (
                                                                    <div className="critic-notes">
                                                                        <div className="critic-notes-label">Feasibility Issues:</div>
                                                                        <ul className="critic-notes-list">
                                                                            {critic.feasibility_issues.map((issue, i) => (
                                                                                <li key={i}>{issue}</li>
                                                                            ))}
                                                                        </ul>
                                                                    </div>
                                                                )}
                                                                {critic.overlap_with_literature && (
                                                                    <div className="critic-notes">
                                                                        <div className="critic-notes-label">Literature Overlap:</div>
                                                                        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                                                                            {critic.overlap_with_literature}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                                {critic.suggested_improvements.length > 0 && (
                                                                    <div className="critic-notes">
                                                                        <div className="critic-notes-label">Suggested Improvements:</div>
                                                                        <ul className="critic-notes-list">
                                                                            {critic.suggested_improvements.map((s, i) => (
                                                                                <li key={i}>{s}</li>
                                                                            ))}
                                                                        </ul>
                                                                    </div>
                                                                )}
                                                            </>
                                                        );
                                                    })()}
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
                        alignItems: 'center',
                        marginBottom: 8,
                    }}
                >
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Engine:</span>
                    <button
                        type="button"
                        onClick={() => setSelectedEngine('gpt')}
                        disabled={disabled}
                        style={{
                            border: selectedEngine === 'gpt' ? '1px solid var(--accent-indigo)' : '1px solid var(--border-subtle)',
                            background: selectedEngine === 'gpt' ? 'rgba(99,102,241,0.12)' : 'var(--bg-surface)',
                            color: selectedEngine === 'gpt' ? 'var(--accent-indigo-light)' : 'var(--text-secondary)',
                            borderRadius: 'var(--radius-sm)',
                            padding: '4px 10px',
                            fontSize: 12,
                            cursor: disabled ? 'not-allowed' : 'pointer',
                        }}
                    >
                        GPT
                    </button>
                    <button
                        type="button"
                        onClick={() => setSelectedEngine('claude')}
                        disabled={disabled}
                        style={{
                            border: selectedEngine === 'claude' ? '1px solid var(--accent-indigo)' : '1px solid var(--border-subtle)',
                            background: selectedEngine === 'claude' ? 'rgba(99,102,241,0.12)' : 'var(--bg-surface)',
                            color: selectedEngine === 'claude' ? 'var(--accent-indigo-light)' : 'var(--text-secondary)',
                            borderRadius: 'var(--radius-sm)',
                            padding: '4px 10px',
                            fontSize: 12,
                            cursor: disabled ? 'not-allowed' : 'pointer',
                        }}
                    >
                        Claude
                    </button>
                    {pipelineOutput?.engine_used && (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>
                            Last run: {pipelineOutput.engine_used.toUpperCase()}
                        </span>
                    )}
                </div>
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
