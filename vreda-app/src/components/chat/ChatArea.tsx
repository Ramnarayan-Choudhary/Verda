'use client';

import { useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import type { Message } from '@/types';
import type { PaperMetadata } from '@/lib/literature/types';
import { FlaskConical, Upload, BookOpen } from 'lucide-react';

interface ChatAreaProps {
    messages: Message[];
    isLoading: boolean;
    streamingText: string;
    onSelectHypothesis?: (hypothesisId: string) => void;
    onRefineHypotheses?: (message: string) => void;
    onApproveBudget?: () => void;
    onImportPaper?: (paper: PaperMetadata) => void;
    importingPaper?: string | null;
    strategistLoading?: boolean;
}

export default function ChatArea({
    messages,
    isLoading,
    streamingText,
    onSelectHypothesis,
    onRefineHypotheses,
    onApproveBudget,
    onImportPaper,
    importingPaper,
    strategistLoading = false,
}: ChatAreaProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, streamingText]);

    if (messages.length === 0 && !isLoading) {
        return (
            <div className="messages-area">
                <div className="empty-state">
                    <div className="empty-state-icon">
                        <FlaskConical size={36} color="var(--accent-indigo-light)" />
                    </div>
                    <h2>Begin Your Research Quest</h2>
                    <p>
                        Upload a research paper (PDF) or paste an arXiv ID to get started.
                        VREDA.ai will analyze it, extract the hypothesis, variables, and
                        generate a complete Research Manifest with execution steps and budget estimates.
                    </p>
                    <div
                        style={{
                            display: 'flex',
                            gap: 12,
                            marginTop: 24,
                            flexWrap: 'wrap',
                            justifyContent: 'center',
                        }}
                    >
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '8px 16px',
                                background: 'var(--bg-surface)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: 13,
                                color: 'var(--text-secondary)',
                            }}
                        >
                            <Upload size={14} />
                            Upload PDF
                        </div>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '8px 16px',
                                background: 'var(--bg-surface)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: 13,
                                color: 'var(--text-secondary)',
                            }}
                        >
                            <BookOpen size={14} />
                            Paste arXiv ID
                        </div>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '8px 16px',
                                background: 'var(--bg-surface)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: 13,
                                color: 'var(--text-secondary)',
                            }}
                        >
                            <FlaskConical size={14} />
                            Get Manifest
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="messages-area">
            {messages.map((msg) => (
                <MessageBubble
                    key={msg.id}
                    message={msg}
                    onSelectHypothesis={onSelectHypothesis}
                    onRefineHypotheses={onRefineHypotheses}
                    onApproveBudget={onApproveBudget}
                    onImportPaper={onImportPaper}
                    importingPaper={importingPaper}
                    strategistLoading={strategistLoading}
                />
            ))}

            {/* Streaming AI response */}
            {streamingText && (
                <div className="message assistant animate-fade-in">
                    <div className="message-avatar">
                        <FlaskConical size={14} />
                    </div>
                    <div className="message-content">
                        {streamingText}
                        <span
                            style={{
                                display: 'inline-block',
                                width: 6,
                                height: 16,
                                background: 'var(--accent-indigo)',
                                marginLeft: 2,
                                animation: 'typing 1s infinite',
                                verticalAlign: 'middle',
                            }}
                        />
                    </div>
                </div>
            )}

            {/* Loading indicator */}
            {isLoading && !streamingText && (
                <div className="message assistant animate-fade-in">
                    <div className="message-avatar">
                        <FlaskConical size={14} />
                    </div>
                    <div className="message-content">
                        <div className="typing-indicator">
                            <div className="typing-dot" />
                            <div className="typing-dot" />
                            <div className="typing-dot" />
                        </div>
                    </div>
                </div>
            )}

            <div ref={bottomRef} />
        </div>
    );
}
