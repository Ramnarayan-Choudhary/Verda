'use client';

import type { ResearchManifest } from '@/types';
import {
    CheckCircle,
    XCircle,
    FlaskConical,
    Beaker,
    DollarSign,
    ListChecks,
    ShieldCheck,
} from 'lucide-react';

interface ManifestCardProps {
    manifest: ResearchManifest;
}

export default function ManifestCard({ manifest }: ManifestCardProps) {
    return (
        <div className="manifest-card">
            <div className="manifest-header">
                <FlaskConical size={18} />
                <h3>Research Manifest</h3>
            </div>

            {/* Hypothesis */}
            <div className="manifest-section">
                <div className="manifest-section-title">
                    <Beaker size={12} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                    Hypothesis
                </div>
                <div className="manifest-hypothesis">{manifest.hypothesis}</div>
            </div>

            {/* Variables */}
            <div className="manifest-section">
                <div className="manifest-section-title">Variables</div>
                <div style={{ marginBottom: 6 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 8 }}>Independent:</span>
                    <div className="manifest-tags" style={{ display: 'inline-flex' }}>
                        {manifest.variables.independent.map((v, i) => (
                            <span key={i} className="manifest-tag var-ind">{v}</span>
                        ))}
                    </div>
                </div>
                <div>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 8 }}>Dependent:</span>
                    <div className="manifest-tags" style={{ display: 'inline-flex' }}>
                        {manifest.variables.dependent.map((v, i) => (
                            <span key={i} className="manifest-tag var-dep">{v}</span>
                        ))}
                    </div>
                </div>
            </div>

            {/* Libraries */}
            <div className="manifest-section">
                <div className="manifest-section-title">Required Libraries</div>
                <div className="manifest-tags">
                    {manifest.libraries.map((lib, i) => (
                        <span key={i} className="manifest-tag library">{lib}</span>
                    ))}
                </div>
            </div>

            {/* Budget */}
            <div className="manifest-section">
                <div className="manifest-section-title">
                    <DollarSign size={12} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                    Budget Estimate
                </div>
                <div className="manifest-budget">
                    <div className="manifest-budget-item">
                        <div className="manifest-budget-value">
                            {manifest.budget_estimate.tokens_used.toLocaleString()}
                        </div>
                        <div className="manifest-budget-label">Tokens</div>
                    </div>
                    <div className="manifest-budget-item">
                        <div className="manifest-budget-value">
                            ${manifest.budget_estimate.estimated_cost_usd.toFixed(4)}
                        </div>
                        <div className="manifest-budget-label">Est. Cost</div>
                    </div>
                </div>
            </div>

            {/* Execution Steps */}
            <div className="manifest-section">
                <div className="manifest-section-title">
                    <ListChecks size={12} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                    Execution Steps
                </div>
                <ol className="manifest-steps">
                    {manifest.execution_steps.map((step, i) => (
                        <li key={i}>{step}</li>
                    ))}
                </ol>
            </div>

            {/* Anti-Gravity Check */}
            <div className="manifest-section">
                <div className="manifest-section-title">
                    <ShieldCheck size={12} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                    Anti-Gravity Audit
                </div>
                <div
                    className={`manifest-audit ${manifest.anti_gravity_check.passed ? 'passed' : 'failed'
                        }`}
                >
                    {manifest.anti_gravity_check.passed ? (
                        <>
                            <CheckCircle size={16} />
                            All checks passed — no physical/logical violations detected.
                        </>
                    ) : (
                        <>
                            <XCircle size={16} />
                            Violations found: {manifest.anti_gravity_check.violations.join(', ')}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
