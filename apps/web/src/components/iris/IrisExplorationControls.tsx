'use client';

import { useState } from 'react';
import { Play, Square, Loader2, Zap } from 'lucide-react';

interface IrisExplorationControlsProps {
    onStep: (action: string) => void;
    isLoading: boolean;
    hasIdea: boolean;
}

const ACTIONS = [
    { id: 'generate', label: 'Generate', icon: '✨', description: 'MCTS explore new idea variant' },
    { id: 'review_and_refine', label: 'Review & Refine', icon: '🔍', description: 'Get review, fix weaknesses' },
    { id: 'retrieve_and_refine', label: 'Retrieve & Refine', icon: '📚', description: 'Search papers, improve idea' },
    { id: 'refresh_idea', label: 'Fresh Approach', icon: '🔄', description: 'Generate completely new angle' },
] as const;

export default function IrisExplorationControls({ onStep, isLoading, hasIdea }: IrisExplorationControlsProps) {
    const [autoRunning, setAutoRunning] = useState(false);
    const [autoIterations, setAutoIterations] = useState(3);

    const handleAutoExplore = async () => {
        setAutoRunning(true);
        for (let i = 0; i < autoIterations; i++) {
            if (!autoRunning) break;
            await new Promise<void>((resolve) => {
                onStep('generate');
                setTimeout(resolve, 2000);
            });
        }
        setAutoRunning(false);
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
                <Zap size={14} />
                Exploration Actions
            </div>

            <div style={{ padding: '10px 16px' }}>
                {/* Manual actions */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
                    {ACTIONS.map((action) => (
                        <button
                            key={action.id}
                            onClick={() => onStep(action.id)}
                            disabled={isLoading || !hasIdea}
                            title={action.description}
                            style={{
                                display: 'flex', alignItems: 'center', gap: 6,
                                padding: '8px 10px',
                                borderRadius: 'var(--radius-sm, 6px)',
                                border: '1px solid var(--border-subtle, #1e1e35)',
                                background: 'var(--bg-surface, #0d0d18)',
                                color: 'var(--text-primary, #e8eaf0)',
                                fontSize: 11, cursor: isLoading ? 'wait' : 'pointer',
                                opacity: isLoading || !hasIdea ? 0.5 : 1,
                            }}
                        >
                            {isLoading ? <Loader2 size={12} className="animate-spin" /> : <span>{action.icon}</span>}
                            {action.label}
                        </button>
                    ))}
                </div>

                {/* Auto-explore */}
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm, 6px)',
                    border: '1px solid var(--border-subtle, #1e1e35)',
                    background: 'var(--bg-surface, #0d0d18)',
                }}>
                    <button
                        onClick={autoRunning ? () => setAutoRunning(false) : handleAutoExplore}
                        disabled={isLoading || !hasIdea}
                        style={{
                            display: 'flex', alignItems: 'center', gap: 4,
                            padding: '4px 10px', borderRadius: 4,
                            border: 'none',
                            background: autoRunning ? '#f87171' : 'var(--accent-indigo, #6366f1)',
                            color: '#fff', fontSize: 11, fontWeight: 600,
                            cursor: 'pointer',
                        }}
                    >
                        {autoRunning ? <><Square size={10} /> Stop</> : <><Play size={10} /> Auto Explore</>}
                    </button>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>×</span>
                    <input
                        type="number"
                        min={1}
                        max={10}
                        value={autoIterations}
                        onChange={(e) => setAutoIterations(Number(e.target.value))}
                        style={{
                            width: 36, padding: '2px 6px', textAlign: 'center',
                            borderRadius: 4, border: '1px solid var(--border-subtle)',
                            background: 'transparent', color: 'var(--text-primary)',
                            fontSize: 11,
                        }}
                    />
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>iterations</span>
                </div>
            </div>
        </div>
    );
}
