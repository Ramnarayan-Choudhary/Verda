'use client';

import type { BudgetQuote } from '@/types/strategist';
import {
    Receipt,
    Cpu,
    Database,
    Zap,
    HardDrive,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
} from 'lucide-react';

interface BudgetCardProps {
    budget: BudgetQuote;
    onApprove: () => void;
    disabled?: boolean;
}

export default function BudgetCard({ budget, onApprove, disabled = false }: BudgetCardProps) {
    return (
        <div className="manifest-card">
            <div className="manifest-header">
                <Receipt size={18} />
                <h3>Budget Estimate</h3>
                {budget.free_tier_compatible && (
                    <span
                        className="manifest-tag"
                        style={{
                            marginLeft: 'auto',
                            background: 'rgba(16, 185, 129, 0.15)',
                            color: 'var(--accent-green)',
                            fontSize: 10,
                        }}
                    >
                        FREE TIER OK
                    </span>
                )}
                {!budget.free_tier_compatible && (
                    <span
                        className="manifest-tag"
                        style={{
                            marginLeft: 'auto',
                            background: 'rgba(245, 158, 11, 0.15)',
                            color: 'var(--accent-amber)',
                            fontSize: 10,
                        }}
                    >
                        PAID TIER
                    </span>
                )}
            </div>

            {/* Cost Breakdown */}
            <div className="manifest-section">
                <div className="manifest-section-title">Cost Breakdown</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <CostRow
                        icon={<Zap size={13} />}
                        label="LLM Tokens"
                        detail={`${(budget.token_costs.total_tokens / 1000).toFixed(0)}K tokens`}
                        cost={budget.token_costs.total_usd}
                    />
                    <CostRow
                        icon={<Cpu size={13} />}
                        label="Compute (GPU)"
                        detail={`${budget.compute_costs.gpu_hours}h ${budget.compute_costs.gpu_type}`}
                        cost={budget.compute_costs.total_usd}
                    />
                    <CostRow
                        icon={<Database size={13} />}
                        label="API Calls"
                        detail={`${budget.api_costs.embedding_calls} embed + ${budget.api_costs.llm_calls} LLM`}
                        cost={budget.api_costs.total_usd}
                    />
                    <CostRow
                        icon={<HardDrive size={13} />}
                        label="Storage"
                        detail={`${budget.storage_costs.estimated_gb} GB`}
                        cost={budget.storage_costs.total_usd}
                    />

                    {/* Divider */}
                    <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />

                    {/* Subtotal */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)' }}>
                        <span>Subtotal</span>
                        <span>${budget.summary.subtotal_usd.toFixed(4)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)' }}>
                        <span>Contingency ({budget.summary.contingency_percent}%)</span>
                        <span>+${budget.summary.contingency_usd.toFixed(4)}</span>
                    </div>

                    {/* Total */}
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            fontSize: 14,
                            fontWeight: 700,
                            color: 'var(--text-primary)',
                            padding: '8px 12px',
                            background: 'var(--bg-surface)',
                            borderRadius: 'var(--radius-sm)',
                            marginTop: 4,
                        }}
                    >
                        <span>Total</span>
                        <span style={{ color: 'var(--accent-green)' }}>${budget.summary.total_usd.toFixed(4)}</span>
                    </div>
                </div>
            </div>

            {/* Range */}
            <div className="manifest-section">
                <div style={{ display: 'flex', gap: 16 }}>
                    <div className="manifest-budget-item">
                        <div className="manifest-budget-value" style={{ fontSize: 14 }}>
                            ${budget.summary.min_usd.toFixed(4)}
                        </div>
                        <div className="manifest-budget-label">Minimum</div>
                    </div>
                    <div className="manifest-budget-item">
                        <div className="manifest-budget-value" style={{ fontSize: 14, color: 'var(--accent-indigo-light)' }}>
                            ${budget.summary.total_usd.toFixed(4)}
                        </div>
                        <div className="manifest-budget-label">Expected</div>
                    </div>
                    <div className="manifest-budget-item">
                        <div className="manifest-budget-value" style={{ fontSize: 14, color: 'var(--accent-amber)' }}>
                            ${budget.summary.max_usd.toFixed(4)}
                        </div>
                        <div className="manifest-budget-label">Maximum</div>
                    </div>
                </div>
            </div>

            {/* Free Tier Warnings */}
            {budget.free_tier_warnings.length > 0 && (
                <div className="manifest-section">
                    <div className={`manifest-audit ${budget.free_tier_compatible ? 'passed' : 'failed'}`}>
                        <AlertTriangle size={14} />
                        <span style={{ marginLeft: 4 }}>
                            {budget.free_tier_compatible ? 'Free Tier Notes' : 'Exceeds Free Tier'}
                        </span>
                    </div>
                    <ul style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 16, marginTop: 4 }}>
                        {budget.free_tier_warnings.map((w, i) => (
                            <li key={i}>{w}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Approve Button */}
            <button
                onClick={onApprove}
                disabled={disabled}
                style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: disabled
                        ? 'var(--bg-surface-hover)'
                        : 'linear-gradient(135deg, var(--accent-indigo), var(--accent-indigo-light))',
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    color: disabled ? 'var(--text-muted)' : 'white',
                    fontSize: 14,
                    fontWeight: 600,
                    cursor: disabled ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    transition: 'all 0.2s',
                    marginTop: 4,
                }}
            >
                <CheckCircle size={16} />
                Approve & Proceed to Execution
                <ArrowRight size={14} />
            </button>
        </div>
    );
}

function CostRow({
    icon,
    label,
    detail,
    cost,
}: {
    icon: React.ReactNode;
    label: string;
    detail: string;
    cost: number;
}) {
    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 13,
                padding: '4px 0',
            }}
        >
            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{icon}</span>
            <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{label}</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{detail}</span>
            <span style={{ color: 'var(--text-primary)', fontWeight: 600, minWidth: 60, textAlign: 'right' }}>
                ${cost.toFixed(4)}
            </span>
        </div>
    );
}
