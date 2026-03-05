'use client';

import { CheckCircle, Circle, AlertTriangle, XCircle, Loader } from 'lucide-react';
import type { PipelineProgressEvent, PipelineStep } from '@/types';

const PIPELINE_STEPS: { key: PipelineStep; label: string }[] = [
    { key: 'metadata', label: 'Fetching paper metadata' },
    { key: 'download', label: 'Downloading PDF' },
    { key: 'upload_storage', label: 'Storing PDF' },
    { key: 'extract_text', label: 'Extracting text' },
    { key: 'chunking', label: 'Chunking text' },
    { key: 'embedding', label: 'Embedding chunks' },
    { key: 'storing_chunks', label: 'Saving to database' },
    { key: 'research_intelligence', label: 'Gathering research landscape' },
    { key: 'strategist', label: 'Running AI analysis' },
];

interface PipelineProgressCardProps {
    events: PipelineProgressEvent[];
    title: string;
}

export default function PipelineProgressCard({ events, title }: PipelineProgressCardProps) {
    // Derive step statuses from events
    const seenSteps = new Set<string>();
    const completedSteps = new Set<string>();
    const warningSteps = new Map<string, string>();
    let currentStep: string | null = null;
    let embeddingCurrent = 0;
    let embeddingTotal = 0;
    let hasError = false;
    let errorMessage = '';
    let isComplete = false;

    for (const event of events) {
        if (event.type === 'progress' && event.step) {
            seenSteps.add(event.step);
            // When a new step starts, the previous one is complete
            if (currentStep && currentStep !== event.step) {
                completedSteps.add(currentStep);
            }
            currentStep = event.step;
            if (event.step === 'embedding' && event.current !== undefined) {
                embeddingCurrent = event.current;
                embeddingTotal = event.total || 0;
            }
        } else if (event.type === 'warning' && event.step) {
            warningSteps.set(event.step, event.message);
        } else if (event.type === 'complete') {
            if (currentStep) completedSteps.add(currentStep);
            currentStep = null;
            isComplete = true;
        } else if (event.type === 'error') {
            hasError = true;
            errorMessage = event.message;
        }
    }

    // Filter to show only relevant steps (steps that were seen or are pending after first seen)
    const firstSeenIndex = PIPELINE_STEPS.findIndex(s => seenSteps.has(s.key));
    const lastSeenIndex = PIPELINE_STEPS.findLastIndex(s => seenSteps.has(s.key));
    const visibleSteps = firstSeenIndex >= 0
        ? PIPELINE_STEPS.slice(firstSeenIndex, isComplete || hasError ? lastSeenIndex + 1 : undefined)
        : [];

    return (
        <div className="pipeline-progress-card">
            <div className="pipeline-progress-header">
                {hasError
                    ? <XCircle size={14} />
                    : isComplete
                        ? <CheckCircle size={14} />
                        : <Loader size={14} className="pipeline-spin" />
                }
                <span>{title}</span>
                {isComplete && <span className="pipeline-complete-badge">Complete</span>}
            </div>

            <div className="pipeline-steps-list">
                {visibleSteps.map(step => {
                    const isDone = completedSteps.has(step.key);
                    const isActive = currentStep === step.key;
                    const hasWarning = warningSteps.has(step.key);

                    return (
                        <div
                            key={step.key}
                            className={`pipeline-step ${isDone ? 'complete' : isActive ? 'active' : 'pending'}`}
                        >
                            <span className="pipeline-step-icon">
                                {isDone && !hasWarning && <CheckCircle size={13} />}
                                {isDone && hasWarning && <AlertTriangle size={13} />}
                                {isActive && <div className="spinner-small" />}
                                {!isDone && !isActive && <Circle size={13} />}
                            </span>
                            <span className="pipeline-step-label">{step.label}</span>
                            {step.key === 'embedding' && isActive && embeddingTotal > 0 && (
                                <span className="pipeline-step-counter">
                                    {embeddingCurrent}/{embeddingTotal}
                                </span>
                            )}
                            {step.key === 'embedding' && isDone && embeddingTotal > 0 && (
                                <span className="pipeline-step-counter">
                                    {embeddingTotal}/{embeddingTotal}
                                </span>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Embedding progress bar */}
            {currentStep === 'embedding' && embeddingTotal > 0 && (
                <div className="progress-bar" style={{ margin: '4px 16px 10px' }}>
                    <div
                        className="progress-bar-fill"
                        style={{ width: `${Math.round((embeddingCurrent / embeddingTotal) * 100)}%` }}
                    />
                </div>
            )}

            {/* Warning messages */}
            {Array.from(warningSteps.entries()).map(([stepKey, message]) => (
                <div key={stepKey} className="pipeline-warning">
                    <AlertTriangle size={11} />
                    <span>{message}</span>
                </div>
            ))}

            {/* Error state */}
            {hasError && (
                <div className="pipeline-error">
                    <XCircle size={12} />
                    <span>{errorMessage}</span>
                </div>
            )}
        </div>
    );
}
