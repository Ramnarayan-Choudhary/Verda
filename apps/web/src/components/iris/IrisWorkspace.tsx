'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import IdeaPanel from './IdeaPanel';
import MCTSTreeView from './MCTSTreeView';
import ReviewPanel from './ReviewPanel';
import KnowledgeRetrieval from './KnowledgeRetrieval';
import IrisExplorationControls from './IrisExplorationControls';
import type { IrisReviewScores, IrisMCTSTreeNode, IrisReviewAspectData } from '@/types/iris';
import { AlertCircle, Wifi, WifiOff, Send, RotateCcw, Bot, User } from 'lucide-react';

interface ChatMessage {
    role: 'user' | 'iris' | 'system';
    content: string;
    idea?: string;
    reviewScores?: IrisReviewScores;
    avgScore?: number;
    timestamp: number;
}

interface IrisWorkspaceProps {
    onIdeaUpdate?: (idea: string, scores: IrisReviewScores, avgScore: number) => void;
    onMessage?: (role: 'user' | 'assistant' | 'system', content: string) => void;
}

export default function IrisWorkspace({ onIdeaUpdate, onMessage }: IrisWorkspaceProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [idea, setIdea] = useState('');
    const [reviewScores, setReviewScores] = useState<IrisReviewScores>({});
    const [averageScore, setAverageScore] = useState(0);
    const [treeData, setTreeData] = useState<IrisMCTSTreeNode | null>(null);
    const [currentNodeId, setCurrentNodeId] = useState<string | undefined>();
    const [isLoading, setIsLoading] = useState(false);
    const [irisHealthy, setIrisHealthy] = useState<boolean | null>(null);
    const [activeTab, setActiveTab] = useState<'tree' | 'review' | 'knowledge'>('tree');
    const [draft, setDraft] = useState('');
    const chatEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    const hasStarted = messages.some(m => m.role === 'user');
    const hasIdea = !!idea;

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Check IRIS health on mount
    useEffect(() => {
        const checkHealth = async () => {
            try {
                const res = await fetch('/api/iris/health');
                const data = await res.json();
                setIrisHealthy(data.healthy);
            } catch {
                setIrisHealthy(false);
            }
        };
        checkHealth();
        const interval = setInterval(checkHealth, 30000);
        return () => clearInterval(interval);
    }, []);

    const fetchTree = useCallback(async () => {
        try {
            const res = await fetch('/api/iris/tree');
            if (res.ok) {
                const data = await res.json();
                if (data && data.id) setTreeData(data);
            }
        } catch { /* ignore */ }
    }, []);

    const appendMessage = useCallback((msg: Omit<ChatMessage, 'timestamp'>) => {
        setMessages(prev => [...prev, { ...msg, timestamp: Date.now() }]);
    }, []);

    const handleSend = useCallback(async () => {
        const content = draft.trim();
        if (!content || isLoading || !irisHealthy) return;

        setDraft('');
        setIsLoading(true);

        // Add user message
        appendMessage({ role: 'user', content });
        onMessage?.('user', content);

        try {
            const res = await fetch('/api/iris/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'IRIS request failed');

            const newIdea: string = data.idea || '';
            const newScores: IrisReviewScores = data.review_scores || {};
            const newAvg: number = data.average_score || 0;

            // Update global state
            if (newIdea) {
                setIdea(newIdea);
                setReviewScores(newScores);
                setAverageScore(newAvg);
                onIdeaUpdate?.(newIdea, newScores, newAvg);
                onMessage?.('assistant', newIdea);
            }

            // Add IRIS response as chat message
            appendMessage({
                role: 'iris',
                content: newIdea || 'No idea generated. Please try rephrasing your query.',
                idea: newIdea,
                reviewScores: newScores,
                avgScore: newAvg,
            });

            await fetchTree();
        } catch (err) {
            const errMsg = err instanceof Error ? err.message : 'Unknown error';
            appendMessage({ role: 'system', content: `Error: ${errMsg}` });
        } finally {
            setIsLoading(false);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [draft, isLoading, irisHealthy, appendMessage, fetchTree, onMessage, onIdeaUpdate]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }, [handleSend]);

    const handleReset = useCallback(() => {
        setMessages([]);
        setIdea('');
        setReviewScores({});
        setAverageScore(0);
        setTreeData(null);
        setCurrentNodeId(undefined);
        setDraft('');
        setTimeout(() => inputRef.current?.focus(), 50);
    }, []);

    const handleStep = useCallback(async (action: string) => {
        setIsLoading(true);
        appendMessage({ role: 'system', content: `Running MCTS step: ${action}...` });
        try {
            const res = await fetch('/api/iris/step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, use_mcts: true }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);

            if (data.idea) {
                setIdea(data.idea);
                if (data.review_scores) setReviewScores(data.review_scores);
                if (data.average_score) setAverageScore(data.average_score);
                onIdeaUpdate?.(data.idea, data.review_scores || reviewScores, data.average_score || averageScore);
                appendMessage({
                    role: 'iris',
                    content: data.idea,
                    idea: data.idea,
                    reviewScores: data.review_scores,
                    avgScore: data.average_score,
                });
            }
            if (data.nodeId) setCurrentNodeId(data.nodeId);
            await fetchTree();
        } catch (err) {
            appendMessage({ role: 'system', content: `Step Error: ${err instanceof Error ? err.message : 'Unknown'}` });
        } finally {
            setIsLoading(false);
        }
    }, [appendMessage, fetchTree, onIdeaUpdate, reviewScores, averageScore]);

    const handleNodeSelect = useCallback(async (nodeId: string) => {
        try {
            const res = await fetch('/api/iris/node', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ node_id: nodeId }),
            });
            const data = await res.json();
            if (res.ok) {
                setIdea(data.idea || '');
                setCurrentNodeId(nodeId);
                if (data.review_scores) setReviewScores(data.review_scores);
                if (data.average_score) setAverageScore(data.average_score);
            }
        } catch { /* ignore */ }
    }, []);

    const handleImproveIdea = useCallback(async (acceptedReviews: IrisReviewAspectData[]) => {
        setIsLoading(true);
        appendMessage({ role: 'system', content: 'Improving idea based on review feedback...' });
        try {
            const res = await fetch('/api/iris/improve-idea', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    idea,
                    accepted_reviews: acceptedReviews.map((r) => ({
                        aspect: r.aspect,
                        feedback: r.summary || r.feedback || '',
                        score: r.score,
                    })),
                }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            const improved = data.improved_idea || data.idea;
            if (improved) {
                setIdea(improved);
                if (data.review_scores) setReviewScores(data.review_scores);
                if (data.average_score) setAverageScore(data.average_score);
                appendMessage({ role: 'iris', content: improved, idea: improved });
                onIdeaUpdate?.(improved, data.review_scores || reviewScores, data.average_score || averageScore);
            }
            await fetchTree();
        } catch (err) {
            appendMessage({ role: 'system', content: `Improve Error: ${err instanceof Error ? err.message : 'Unknown'}` });
        } finally {
            setIsLoading(false);
        }
    }, [idea, appendMessage, fetchTree, onIdeaUpdate, reviewScores, averageScore]);

    const handleImproveWithKnowledge = useCallback(async () => {
        setIsLoading(true);
        appendMessage({ role: 'system', content: 'Retrieving knowledge and improving idea...' });
        try {
            const res = await fetch('/api/iris/improve-with-knowledge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            if (data.improved_idea) {
                setIdea(data.improved_idea);
                if (data.review_scores) setReviewScores(data.review_scores);
                if (data.average_score) setAverageScore(data.average_score);
                appendMessage({ role: 'iris', content: data.improved_idea, idea: data.improved_idea });
                onIdeaUpdate?.(data.improved_idea, data.review_scores || reviewScores, data.average_score || averageScore);
            }
            await fetchTree();
        } catch (err) {
            appendMessage({ role: 'system', content: `Knowledge Error: ${err instanceof Error ? err.message : 'Unknown'}` });
        } finally {
            setIsLoading(false);
        }
    }, [idea, appendMessage, fetchTree, onIdeaUpdate, reviewScores, averageScore]);

    const handleRefreshIdea = useCallback(async () => {
        setIsLoading(true);
        appendMessage({ role: 'system', content: 'Generating fresh research idea...' });
        try {
            const res = await fetch('/api/iris/refresh-idea', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            if (data.idea) {
                setIdea(data.idea);
                if (data.review_scores) setReviewScores(data.review_scores);
                if (data.average_score) setAverageScore(data.average_score);
                appendMessage({ role: 'iris', content: data.idea, idea: data.idea });
                onIdeaUpdate?.(data.idea, data.review_scores || reviewScores, data.average_score || averageScore);
            }
            await fetchTree();
        } catch (err) {
            appendMessage({ role: 'system', content: `Refresh Error: ${err instanceof Error ? err.message : 'Unknown'}` });
        } finally {
            setIsLoading(false);
        }
    }, [idea, appendMessage, fetchTree, onIdeaUpdate, reviewScores, averageScore]);

    // Offline state
    if (irisHealthy === false) {
        return (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-secondary, #8b8fa3)' }}>
                <WifiOff size={28} style={{ marginBottom: 10, color: '#f87171' }} />
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>IRIS Service Offline</div>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                    Start the IRIS backend:
                    <br />
                    <code style={{ fontSize: 11, background: 'var(--bg-surface)', padding: '4px 8px', borderRadius: 4, display: 'inline-block', marginTop: 4 }}>
                        cd services/hypothesis-room/iris && python server_wrapper.py
                    </code>
                </div>
            </div>
        );
    }

    const inputPlaceholder = hasStarted
        ? 'Provide feedback or suggestions to refine your research idea...'
        : 'Enter your research goal or question to begin...';

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

            {/* Header */}
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 12px',
                borderBottom: '1px solid var(--border-subtle, #1e1e35)',
                flexShrink: 0,
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                    {irisHealthy ? (
                        <><Wifi size={13} color="#4ade80" /><span style={{ color: '#4ade80', fontWeight: 600 }}>IRIS</span><span style={{ color: 'var(--text-secondary)' }}>· MCTS Ideation Active</span></>
                    ) : (
                        <><AlertCircle size={13} color="#fbbf24" /><span style={{ color: '#fbbf24' }}>Connecting to IRIS...</span></>
                    )}
                </div>
                {hasStarted && (
                    <button
                        onClick={handleReset}
                        title="Start new session"
                        style={{
                            display: 'flex', alignItems: 'center', gap: 4,
                            background: 'none', border: '1px solid var(--border-subtle, #1e1e35)',
                            borderRadius: 6, padding: '3px 10px',
                            fontSize: 11, color: 'var(--text-secondary)',
                            cursor: 'pointer',
                        }}
                    >
                        <RotateCcw size={11} /> New Session
                    </button>
                )}
            </div>

            {/* Main content — scrollable */}
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column' }}>

                {/* Welcome state */}
                {!hasStarted && (
                    <div style={{
                        flex: 1, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center',
                        padding: 24, textAlign: 'center', gap: 12,
                    }}>
                        <div style={{
                            width: 48, height: 48, borderRadius: '50%',
                            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                            <Bot size={24} color="#fff" />
                        </div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>IRIS Research Ideation</div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 320, lineHeight: 1.6 }}>
                            Powered by Monte Carlo Tree Search. Describe your research interest and IRIS will generate, refine, and explore ideas through iterative feedback.
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginTop: 4 }}>
                            {[
                                'Efficient LLM fine-tuning with minimal data',
                                'Multimodal reasoning in vision-language models',
                                'Reducing hallucinations in RAG systems',
                                'Protein structure prediction for drug discovery',
                            ].map((s) => (
                                <button
                                    key={s}
                                    onClick={() => setDraft(s)}
                                    style={{
                                        padding: '4px 10px', fontSize: 11, borderRadius: 12,
                                        border: '1px solid var(--border-subtle, #1e1e35)',
                                        background: 'transparent', color: 'var(--text-secondary)',
                                        cursor: 'pointer',
                                    }}
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Chat history */}
                {hasStarted && (
                    <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {messages.map((msg, i) => (
                            <div key={i} style={{
                                display: 'flex',
                                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                                gap: 8,
                                alignItems: 'flex-start',
                            }}>
                                {/* Avatar */}
                                {msg.role !== 'system' && (
                                    <div style={{
                                        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        background: msg.role === 'user'
                                            ? 'var(--accent-indigo, #6366f1)'
                                            : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                                    }}>
                                        {msg.role === 'user'
                                            ? <User size={14} color="#fff" />
                                            : <Bot size={14} color="#fff" />}
                                    </div>
                                )}

                                {/* Bubble */}
                                <div style={{
                                    maxWidth: msg.role === 'system' ? '100%' : '85%',
                                    padding: msg.role === 'system' ? '4px 10px' : '10px 14px',
                                    borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                                    background: msg.role === 'user'
                                        ? 'var(--accent-indigo, #6366f1)'
                                        : msg.role === 'system'
                                            ? 'transparent'
                                            : 'var(--bg-elevated, #12121f)',
                                    border: msg.role === 'iris'
                                        ? '1px solid var(--border-subtle, #1e1e35)'
                                        : msg.role === 'system'
                                            ? '1px dashed var(--border-subtle, #1e1e35)'
                                            : 'none',
                                    width: msg.role === 'system' ? '100%' : undefined,
                                }}>
                                    {msg.role === 'iris' && (
                                        <div style={{ fontSize: 9, color: 'var(--text-secondary)', marginBottom: 4, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                                            IRIS · Generated Idea
                                        </div>
                                    )}
                                    <div style={{
                                        fontSize: 12, lineHeight: 1.65,
                                        color: msg.role === 'user'
                                            ? '#fff'
                                            : msg.role === 'system'
                                                ? 'var(--text-secondary)'
                                                : 'var(--text-primary)',
                                        fontStyle: msg.role === 'system' ? 'italic' : undefined,
                                        whiteSpace: 'pre-wrap',
                                    }}>
                                        {msg.content}
                                    </div>
                                    {msg.role === 'iris' && msg.avgScore !== undefined && msg.avgScore > 0 && (
                                        <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                            <span style={{
                                                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                                                background: msg.avgScore >= 7 ? '#166534' : msg.avgScore >= 5 ? '#854d0e' : '#7f1d1d',
                                                color: '#fff', fontWeight: 600,
                                            }}>
                                                Score: {msg.avgScore.toFixed(1)}/10
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}

                        {/* Loading indicator */}
                        {isLoading && (
                            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                                <div style={{
                                    width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                }}>
                                    <Bot size={14} color="#fff" />
                                </div>
                                <div style={{
                                    padding: '10px 14px', borderRadius: '14px 14px 14px 4px',
                                    background: 'var(--bg-elevated, #12121f)',
                                    border: '1px solid var(--border-subtle, #1e1e35)',
                                    display: 'flex', gap: 4, alignItems: 'center',
                                }}>
                                    {[0, 1, 2].map(i => (
                                        <span key={i} style={{
                                            width: 6, height: 6, borderRadius: '50%',
                                            background: '#6366f1', display: 'inline-block',
                                            animation: `iris-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                                        }} />
                                    ))}
                                </div>
                            </div>
                        )}

                        <div ref={chatEndRef} />
                    </div>
                )}

                {/* Idea Panel — after first idea */}
                {hasIdea && (
                    <div style={{ padding: '0 16px', flexShrink: 0 }}>
                        <IdeaPanel
                            idea={idea}
                            reviewScores={reviewScores}
                            averageScore={averageScore}
                            onRefreshIdea={handleRefreshIdea}
                            isLoading={isLoading}
                        />
                    </div>
                )}

                {/* Exploration Controls */}
                {hasIdea && (
                    <div style={{ padding: '8px 16px', flexShrink: 0 }}>
                        <IrisExplorationControls
                            onStep={handleStep}
                            isLoading={isLoading}
                            hasIdea={hasIdea}
                        />
                    </div>
                )}

                {/* Tabs */}
                {hasIdea && (
                    <div style={{ padding: '0 16px 16px', flexShrink: 0 }}>
                        <div style={{
                            display: 'flex', gap: 2,
                            background: 'var(--bg-surface, #0d0d18)',
                            borderRadius: 'var(--radius-sm, 6px)', padding: 2, marginBottom: 10,
                        }}>
                            {(['tree', 'review', 'knowledge'] as const).map((tab) => (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab)}
                                    style={{
                                        flex: 1, padding: '6px 0', borderRadius: 4,
                                        border: 'none', fontSize: 11, fontWeight: 500,
                                        cursor: 'pointer', textTransform: 'capitalize',
                                        background: activeTab === tab ? 'var(--bg-elevated, #12121f)' : 'transparent',
                                        color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-secondary)',
                                    }}
                                >
                                    {tab === 'tree' ? '🌳 Tree' : tab === 'review' ? '🔍 Review' : '📚 Knowledge'}
                                </button>
                            ))}
                        </div>
                        {activeTab === 'tree' && (
                            <MCTSTreeView treeData={treeData} onNodeSelect={handleNodeSelect} currentNodeId={currentNodeId} />
                        )}
                        {activeTab === 'review' && (
                            <ReviewPanel idea={idea} onImproveIdea={handleImproveIdea} isLoading={isLoading} />
                        )}
                        {activeTab === 'knowledge' && (
                            <KnowledgeRetrieval idea={idea} onImproveWithKnowledge={handleImproveWithKnowledge} isLoading={isLoading} />
                        )}
                    </div>
                )}
            </div>

            {/* Chat input — always visible at bottom */}
            <div style={{
                padding: '10px 12px',
                borderTop: '1px solid var(--border-subtle, #1e1e35)',
                background: 'var(--bg-surface, #0d0d18)',
                flexShrink: 0,
            }}>
                <div style={{
                    display: 'flex', gap: 8, alignItems: 'flex-end',
                    background: 'var(--bg-elevated, #12121f)',
                    border: '1px solid var(--border-subtle, #1e1e35)',
                    borderRadius: 12, padding: '8px 12px',
                }}>
                    <textarea
                        ref={inputRef}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={inputPlaceholder}
                        disabled={!irisHealthy || isLoading}
                        rows={1}
                        style={{
                            flex: 1, background: 'transparent', border: 'none',
                            outline: 'none', resize: 'none', overflowY: 'auto',
                            maxHeight: 120, minHeight: 20,
                            fontSize: 13, color: 'var(--text-primary)',
                            lineHeight: 1.5, padding: 0,
                            fontFamily: 'inherit',
                        }}
                        onInput={(e) => {
                            const t = e.currentTarget;
                            t.style.height = 'auto';
                            t.style.height = Math.min(t.scrollHeight, 120) + 'px';
                        }}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!draft.trim() || !irisHealthy || isLoading}
                        style={{
                            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: draft.trim() && !isLoading ? '#6366f1' : 'var(--bg-surface)',
                            border: 'none', cursor: draft.trim() ? 'pointer' : 'default',
                            color: draft.trim() && !isLoading ? '#fff' : 'var(--text-secondary)',
                            transition: 'background 0.15s',
                        }}
                    >
                        <Send size={14} />
                    </button>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4, textAlign: 'center' }}>
                    {hasStarted ? 'Shift+Enter for newline · Enter to send' : 'Enter to start IRIS MCTS ideation'}
                </div>
            </div>

            {/* Bounce animation */}
            <style>{`
                @keyframes iris-bounce {
                    0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
                    40% { transform: translateY(-6px); opacity: 1; }
                }
            `}</style>
        </div>
    );
}

export type { IrisWorkspaceProps };
