'use client';

import { useState } from 'react';
import type { PaperAnalysis } from '@/types/strategist';
import {
    FileText,
    AlertTriangle,
    CheckCircle,
    BookOpen,
    Database,
    BarChart3,
    Lightbulb,
    Cpu,
    ChevronDown,
    ChevronRight,
    Sigma,
} from 'lucide-react';

interface PaperAnalysisCardProps {
    analysis: PaperAnalysis;
}

/**
 * Clean up titles from PDF extraction artifacts:
 * - Fix ALL CAPS
 * - Fix jammed words (common PDF line-break artifacts)
 * - Fix hyphenation artifacts
 */
function cleanTitle(title: string): string {
    // Fix hyphenation artifacts: "BAL-ANCING" -> "BALANCING"
    let cleaned = title.replace(/(\w)-\s*\n?\s*(\w)/g, '$1$2');

    // If mostly uppercase, convert to title case
    const upperCount = (cleaned.match(/[A-Z]/g) || []).length;
    const letterCount = (cleaned.match(/[a-zA-Z]/g) || []).length;
    if (letterCount > 0 && upperCount / letterCount > 0.6) {
        cleaned = cleaned
            .toLowerCase()
            .replace(/(?:^|\s|[-:,])\s*\w/g, (match) => match.toUpperCase());
    }

    // Fix common jammed patterns: insert space before capital letter runs
    // e.g., "ForLow" -> "For Low", "DimensionalGenerative" stays
    cleaned = cleaned.replace(/([a-z])([A-Z][a-z])/g, '$1 $2');

    return cleaned.trim();
}

const domainLabels: Record<string, string> = {
    cv: 'Computer Vision',
    nlp: 'NLP',
    ml: 'Machine Learning',
    robotics: 'Robotics',
    other: 'Research',
};

export default function PaperAnalysisCard({ analysis }: PaperAnalysisCardProps) {
    const [showAllEquations, setShowAllEquations] = useState(false);

    const riskLevel = analysis.hallucination_risk.level;
    const riskConfig = {
        low: { color: 'var(--accent-green)', bg: 'rgba(16,185,129,0.08)', icon: CheckCircle },
        medium: { color: 'var(--accent-amber)', bg: 'rgba(245,158,11,0.08)', icon: AlertTriangle },
        high: { color: 'var(--accent-red)', bg: 'rgba(239,68,68,0.08)', icon: AlertTriangle },
    }[riskLevel];
    const RiskIcon = riskConfig.icon;

    const visibleEquations = showAllEquations ? analysis.equations : analysis.equations.slice(0, 3);
    const hasMoreEquations = analysis.equations.length > 3;
    const metricsWithValues = analysis.metrics.filter(m => m.value && m.value !== 'N/A' && m.value !== '');
    const metricsWithoutValues = analysis.metrics.filter(m => !m.value || m.value === 'N/A' || m.value === '');

    return (
        <div className="paper-card">
            {/* Header Bar */}
            <div className="paper-card-header">
                <div className="paper-card-header-left">
                    <FileText size={16} />
                    <span className="paper-card-label">Paper Analysis</span>
                </div>
                <div className="paper-card-header-right">
                    <span className="paper-card-domain">{domainLabels[analysis.domain] || analysis.domain}</span>
                    <span
                        className="paper-card-risk-badge"
                        style={{ color: riskConfig.color, background: riskConfig.bg }}
                    >
                        <RiskIcon size={10} />
                        {riskLevel.toUpperCase()} RISK
                    </span>
                </div>
            </div>

            {/* Title Block */}
            <div className="paper-card-title-block">
                <h3 className="paper-card-title">{cleanTitle(analysis.title)}</h3>
                {analysis.authors.length > 0 && (
                    <div className="paper-card-authors">
                        {analysis.authors.join(', ')}
                    </div>
                )}
            </div>

            {/* Summary */}
            {analysis.abstract_summary && (
                <div className="paper-card-summary">
                    <p>{analysis.abstract_summary}</p>
                </div>
            )}

            {/* Two-column grid: Key Claims + Architecture */}
            <div className="paper-card-grid">
                {/* Key Claims */}
                {analysis.key_claims.length > 0 && (
                    <div className="paper-card-section">
                        <div className="paper-card-section-header">
                            <Lightbulb size={12} />
                            Key Claims
                        </div>
                        <ul className="paper-card-claims">
                            {analysis.key_claims.map((claim, i) => (
                                <li key={i}>{claim}</li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Architecture */}
                {analysis.model_architecture && (
                    <div className="paper-card-section">
                        <div className="paper-card-section-header">
                            <Cpu size={12} />
                            Architecture
                        </div>
                        <div className="paper-card-arch-name">{analysis.model_architecture.name}</div>
                        {analysis.model_architecture.layers.length > 0 && (
                            <div className="paper-card-chip-row">
                                {analysis.model_architecture.layers.map((layer, i) => (
                                    <span key={i} className="paper-card-chip chip-indigo">{layer}</span>
                                ))}
                            </div>
                        )}
                        {Object.keys(analysis.model_architecture.hyperparameters).length > 0 && (
                            <div className="paper-card-kv-list">
                                {Object.entries(analysis.model_architecture.hyperparameters).slice(0, 4).map(([k, v]) => (
                                    <div key={k} className="paper-card-kv">
                                        <span className="paper-card-kv-key">{k}</span>
                                        <span className="paper-card-kv-val">{v}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Datasets + Metrics Row */}
            <div className="paper-card-grid">
                {/* Datasets */}
                {analysis.datasets.length > 0 && (
                    <div className="paper-card-section">
                        <div className="paper-card-section-header">
                            <Database size={12} />
                            Datasets
                        </div>
                        <div className="paper-card-chip-row">
                            {analysis.datasets.map((ds, i) => (
                                <span key={i} className="paper-card-chip chip-cyan" title={`${ds.size} — ${ds.source}`}>
                                    {ds.name}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Metrics */}
                {analysis.metrics.length > 0 && (
                    <div className="paper-card-section">
                        <div className="paper-card-section-header">
                            <BarChart3 size={12} />
                            Metrics
                        </div>
                        {/* Metrics with actual values → stat display */}
                        {metricsWithValues.length > 0 && (
                            <div className="paper-card-metrics-grid">
                                {metricsWithValues.map((m, i) => (
                                    <div key={i} className="paper-card-metric">
                                        <div className="paper-card-metric-value">{m.value}</div>
                                        <div className="paper-card-metric-name">{m.name}</div>
                                        {m.comparison && (
                                            <div className="paper-card-metric-cmp">{m.comparison}</div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                        {/* Metrics without values → tags */}
                        {metricsWithoutValues.length > 0 && (
                            <div className="paper-card-chip-row" style={{ marginTop: metricsWithValues.length > 0 ? 6 : 0 }}>
                                {metricsWithoutValues.map((m, i) => (
                                    <span key={i} className="paper-card-chip chip-amber">{m.name}</span>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Equations — collapsible */}
            {analysis.equations.length > 0 && (
                <div className="paper-card-section paper-card-equations-section">
                    <button
                        className="paper-card-section-header paper-card-toggle"
                        onClick={() => setShowAllEquations(!showAllEquations)}
                    >
                        <Sigma size={12} />
                        Equations ({analysis.equations.length})
                        {hasMoreEquations && (
                            showAllEquations
                                ? <ChevronDown size={12} style={{ marginLeft: 'auto' }} />
                                : <ChevronRight size={12} style={{ marginLeft: 'auto' }} />
                        )}
                    </button>
                    <div className="paper-card-equations">
                        {visibleEquations.map((eq, i) => (
                            <div key={i} className="paper-card-equation">
                                <code>{eq.latex}</code>
                                <span className="paper-card-eq-desc">{eq.description}</span>
                            </div>
                        ))}
                    </div>
                    {hasMoreEquations && !showAllEquations && (
                        <button
                            className="paper-card-show-more"
                            onClick={() => setShowAllEquations(true)}
                        >
                            Show {analysis.equations.length - 3} more equations
                        </button>
                    )}
                </div>
            )}

            {/* Hallucination Risk Footer */}
            {analysis.hallucination_risk.reasons.length > 0 && (
                <div className="paper-card-risk-footer">
                    <BookOpen size={11} />
                    {analysis.hallucination_risk.reasons.slice(0, 2).join(' · ')}
                </div>
            )}
        </div>
    );
}
