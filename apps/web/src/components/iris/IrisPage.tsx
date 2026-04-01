'use client';

/**
 * IrisPage — full-page IRIS workspace replicating the original 3-column layout:
 *   Left:   IRIS branding + literature Q&A history + search bar
 *   Center: Toolbar + sticky proposal box + chat messages + input
 *   Right:  Research Brief + score + idea text + review controls
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { IrisReviewScores, IrisMCTSTreeNode } from '@/types/iris';
import { ArrowLeft, RefreshCw, Search, Zap, ChevronRight, Star, BookOpen, RotateCcw, Paperclip, WifiOff, FileText } from 'lucide-react';

// ── URL / arXiv detection helpers ──────────────────────────────────────────
const ARXIV_RE = /https?:\/\/(?:www\.)?arxiv\.org\/(?:abs|pdf)\/([\d.v]+)/i;
const URL_RE   = /https?:\/\/[^\s]+/g;

function extractArxivId(text: string): string | null {
    const m = text.match(ARXIV_RE);
    return m ? m[1] : null;
}

function extractUrls(text: string): string[] {
    return text.match(URL_RE) ?? [];
}

interface ChatMsg { role: 'user' | 'assistant' | 'system'; content: string; }
interface QAItem  { query: string; answer: string; }

/**
 * IRIS backend can return idea as a plain string OR a structured object
 * like { title, content } or { title, experiment_plan, proposed_method, ... }.
 * Normalize everything to a plain markdown string for rendering.
 */
function formatIdeaObject(obj: Record<string, unknown>): string {
    // Prefer pre-formatted content field
    if (obj.content && typeof obj.content === 'string' && obj.content.trim()) return obj.content.trim();
    // Build clean markdown from structured fields
    const parts: string[] = [];
    if (obj.title) parts.push(`# ${obj.title}\n`);
    if (obj.proposed_method) parts.push(`## Proposed Method\n\n${obj.proposed_method}\n`);
    if (obj.experiment_plan) parts.push(`## Experiment Plan\n\n${obj.experiment_plan}\n`);
    if (obj.test_case_examples) parts.push(`## Test Cases\n\n${obj.test_case_examples}\n`);
    if (parts.length > 0) return parts.join('\n');
    // Check for any other non-empty string fields as fallback
    const fallback = Object.values(obj).find(v => typeof v === 'string' && (v as string).length > 50);
    if (fallback) return fallback as string;
    return JSON.stringify(obj, null, 2);
}

function normalizeIdea(raw: unknown): string {
    if (!raw) return '';
    if (typeof raw === 'string') {
        const s = raw.trim();
        if (!s) return '';
        // Try to parse as JSON — LLM sometimes returns a JSON string instead of object
        if (s.startsWith('{') || s.startsWith('[')) {
            try {
                const parsed = JSON.parse(s);
                if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'object') {
                    // Array of idea objects — take first one
                    return formatIdeaObject(parsed[0] as Record<string, unknown>);
                }
                if (typeof parsed === 'object' && parsed !== null) {
                    return formatIdeaObject(parsed as Record<string, unknown>);
                }
            } catch { /* not JSON, use as-is */ }
        }
        // Strip raw JSON artifacts that sometimes leak into plain text responses
        // e.g. lines that are just `[` or `{` at the start
        if (/^\[\s*\{/.test(s)) {
            // Try extracting just the JSON block
            const jsonEnd = s.lastIndexOf('}') + 1;
            if (jsonEnd > 0) {
                const jsonCandidate = s.slice(s.indexOf('['), jsonEnd + 1).replace(/\]$/, '') + '}';
                try {
                    const parsed = JSON.parse(jsonCandidate) as Record<string, unknown>;
                    return formatIdeaObject(parsed);
                } catch { /* fallback below */ }
            }
        }
        return s;
    }
    if (typeof raw === 'object' && raw !== null) {
        if (Array.isArray(raw) && raw.length > 0) return formatIdeaObject(raw[0] as Record<string, unknown>);
        return formatIdeaObject(raw as Record<string, unknown>);
    }
    return String(raw);
}

interface IrisPageProps {
    onBack: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function Score({ value }: { value: number }) {
    const color = value >= 7 ? '#16a34a' : value >= 5 ? '#d97706' : value > 0 ? '#dc2626' : '#94a3b8';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color }}>
            <Star size={13} fill={value > 0 ? color : 'none'} stroke={color} />
            Score: {value > 0 ? `${value.toFixed(1)}/10` : '—'}
        </div>
    );
}

function TypingDots() {
    return (
        <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}>
            {[0, 1, 2].map(i => (
                <span key={i} style={{
                    width: 5, height: 5, borderRadius: '50%', background: '#94a3b8',
                    display: 'inline-block',
                    animation: `irisTyping 1.2s ease-in-out ${i * 0.2}s infinite`,
                }} />
            ))}
            <style>{`@keyframes irisTyping{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-5px);opacity:1}}`}</style>
        </span>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function IrisPage({ onBack }: IrisPageProps) {
    // Chat state
    const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([]);
    const [draft, setDraft] = useState('');
    const [loading, setLoading] = useState(false);
    const [paperTitle, setPaperTitle] = useState<string | null>(null); // currently loaded paper

    // Idea / review state
    const [idea, setIdea] = useState('');
    const [reviewScores, setReviewScores] = useState<IrisReviewScores>({});
    const [reviewFeedback, setReviewFeedback] = useState<Record<string, string>>({});
    const [avgScore, setAvgScore] = useState(0);

    // Hypothesis history — all generated/refined ideas for the current session
    interface IdeaVersion { id: string; content: string; scores: IrisReviewScores; avgScore: number; ts: number; }
    const [ideaHistory, setIdeaHistory] = useState<IdeaVersion[]>([]);
    const [showHistory, setShowHistory] = useState(false);
    const [historyModal, setHistoryModal] = useState<IdeaVersion | null>(null);
    const [leftTab, setLeftTab] = useState<'sessions' | 'literature'>('sessions');
    const [treeData, setTreeData] = useState<IrisMCTSTreeNode | null>(null);

    // Review navigation
    const reviewAspects = Object.keys(reviewScores);
    const [reviewIdx, setReviewIdx] = useState(0);
    const currentAspect = reviewAspects[reviewIdx] ?? '';
    // reviewScores values are plain numbers; reviewFeedback holds the textual feedback
    const currentScore = currentAspect ? ((reviewScores as Record<string, number>)[currentAspect] ?? 0) : 0;
    const currentFeedbackText = currentAspect ? (reviewFeedback[currentAspect] ?? '') : '';

    // Q&A (literature retrieval) state
    const [qaItems, setQaItems] = useState<QAItem[]>([]);
    const [qaSearch, setQaSearch] = useState('');
    const [qaLoading, setQaLoading] = useState(false);

    // Health
    const [healthy, setHealthy] = useState<boolean | null>(null);

    // Auto-generate
    const [autoGenerate, setAutoGenerate] = useState(false);
    const autoRef = useRef<ReturnType<typeof setInterval> | null>(null);
    // Refs that always hold the latest values — used inside interval to avoid stale closures
    const loadingRef = useRef(false);
    const ideaRef = useRef('');
    const autoGenerateRef = useRef(false);

    // Show tree panel
    const [showTree, setShowTree] = useState(false);

    // Refs
    const chatEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    // Always-current ref to handleStep so the interval never captures a stale closure
    const handleStepRef = useRef<(action: string) => Promise<void>>(() => Promise.resolve());

    const hasStarted = chatMsgs.some(m => m.role === 'user');
    const inputPlaceholder = hasStarted
        ? 'Provide feedback, or paste a new arXiv URL to switch papers...'
        : 'Enter a research goal, or paste an arXiv URL (e.g. https://arxiv.org/abs/2502.09858)...';

    // ── Health check ──
    useEffect(() => {
        const check = async () => {
            try {
                const r = await fetch('/api/iris/health');
                const d = await r.json();
                setHealthy(d.healthy);
            } catch { setHealthy(false); }
        };
        check();
        const t = setInterval(check, 30000);
        return () => clearInterval(t);
    }, []);

    // ── Keep refs in sync with state ──
    useEffect(() => { loadingRef.current = loading; }, [loading]);
    useEffect(() => { ideaRef.current = idea; }, [idea]);
    useEffect(() => { autoGenerateRef.current = autoGenerate; }, [autoGenerate]);

    // ── Auto-scroll ──
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatMsgs, loading]);

    // ── Auto-generate interval — uses refs to avoid stale closures ──
    useEffect(() => {
        if (autoGenerate && idea) {
            if (autoRef.current) clearInterval(autoRef.current);
            autoRef.current = setInterval(() => {
                // Always read current values from refs — never stale
                if (!loadingRef.current && ideaRef.current && autoGenerateRef.current) {
                    handleStepRef.current('generate');
                }
            }, 10000); // 10s gives LLM calls time to complete
        } else {
            if (autoRef.current) { clearInterval(autoRef.current); autoRef.current = null; }
        }
        return () => { if (autoRef.current) { clearInterval(autoRef.current); autoRef.current = null; } };
    }, [autoGenerate, idea]);

    // ── Reset review index when scores change ──
    useEffect(() => { setReviewIdx(0); }, [reviewScores]);

    // ── Helpers ──
    const addMsg = useCallback((role: ChatMsg['role'], content: string) => {
        setChatMsgs(prev => [...prev, { role, content }]);
    }, []);

    const updateIdea = useCallback((data: { idea?: unknown; review_scores?: IrisReviewScores; average_score?: number; review_feedback?: Record<string, string> }) => {
        const ideaText = data.idea != null ? normalizeIdea(data.idea) : '';
        const isRealIdea = !!ideaText && !ideaText.startsWith('[IRIS could not');

        if (ideaText) {
            setIdea(ideaText);
            if (isRealIdea) {
                const snapScores = data.review_scores ?? {};
                const snapAvg = data.average_score ?? 0;
                setIdeaHistory(prev => {
                    if (prev.length > 0 && prev[prev.length - 1].content === ideaText) return prev;
                    return [...prev, { id: `v${prev.length + 1}`, content: ideaText, scores: snapScores, avgScore: snapAvg, ts: Date.now() }];
                });
            }
        }
        // Only set scores/feedback when we have a real idea — prevents 1.0 scores from error runs
        if (isRealIdea) {
            if (data.review_scores && Object.keys(data.review_scores).length > 0) setReviewScores(data.review_scores);
            if (data.average_score != null) setAvgScore(data.average_score);
        }
        if (data.review_feedback && typeof data.review_feedback === 'object' && Object.keys(data.review_feedback).length > 0) {
            setReviewFeedback(prev => ({ ...prev, ...(data.review_feedback as Record<string, string>) }));
        }
    }, []);

    const fetchTree = useCallback(async () => {
        try {
            const r = await fetch('/api/iris/tree');
            if (r.ok) { const d = await r.json(); if (d?.id) setTreeData(d); }
        } catch { /* ignore */ }
    }, []);

    // ── Reset IRIS backend + local state ──
    const resetIrisSession = useCallback(async () => {
        await fetch('/api/iris/reset', { method: 'POST' }).catch(() => {});
        setIdea('');
        setReviewScores({});
        setReviewFeedback({});
        setAvgScore(0);
        setTreeData(null);
        setPaperTitle(null);
        setIdeaHistory([]);
    }, []);

    // ── Load arXiv paper into IRIS via metadata (no PDF download required) ──
    const loadArxivPaper = useCallback(async (url: string): Promise<string | null> => {
        addMsg('system', 'Loading paper from arXiv…');
        try {
            const r = await fetch('/api/iris/load-arxiv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            });
            let d: Record<string, unknown> = {};
            try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}` }; }
            if (!r.ok) throw new Error((d.error as string) || `Failed to load paper (HTTP ${r.status})`);
            const title = (d.title as string) || 'Loaded paper';
            addMsg('system', `Paper loaded: "${title}"`);
            return title;
        } catch (err) {
            addMsg('system', `Paper load error: ${err instanceof Error ? err.message : String(err)}`);
            return null; // null = failed; caller must not proceed to chat
        }
    }, [addMsg]);

    // ── Send chat message ──
    const handleSend = useCallback(async () => {
        const content = draft.trim();
        if (!content || loading || !healthy) return;
        setDraft('');
        setLoading(true);
        addMsg('user', content);

        try {
            // ── Detect URLs (arXiv or other PDF links) ─────────────────────
            const urls = extractUrls(content);
            const arxivUrl = urls.find(u => ARXIV_RE.test(u));
            const pdfUrl   = !arxivUrl ? urls.find(u => u.endsWith('.pdf')) : null;
            const paperUrl = arxivUrl || pdfUrl;

            if (paperUrl) {
                // Reset IRIS session so old paper context is fully cleared
                await resetIrisSession();
                // Clear local chat history except the user message just added
                setChatMsgs(prev => prev.filter(m => m.role === 'user').slice(-1));

                // Load paper metadata into IRIS knowledge store
                const title = await loadArxivPaper(paperUrl);
                if (!title) {
                    // Paper load failed — stop here rather than sending stale context to IRIS
                    setLoading(false);
                    return;
                }
                setPaperTitle(title);

                // Strip URLs from the prompt — keep only the research intent text
                const intent = content.replace(URL_RE, '').replace(/\s+/g, ' ').trim()
                    || 'Generate impactful and novel hypotheses based on this paper.';

                // Send intent to IRIS — force_init:true ensures the backend re-initializes
                // with the newly loaded paper context even if current_root was stale
                const r = await fetch('/api/iris/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: intent, force_init: true }),
                });
                let d: Record<string, unknown> = {};
                try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}: non-JSON response` }; }
                if (!r.ok) throw new Error((d.error as string) || `HTTP ${r.status}`);
                updateIdea(d as Parameters<typeof updateIdea>[0]);
                const ideaText = normalizeIdea(d.idea);
                if (ideaText) addMsg('assistant', ideaText);
                await fetchTree();
                return;
            }

            // ── Normal chat (no URL) ────────────────────────────────────────
            const r = await fetch('/api/iris/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content }),
            });
            let d: Record<string, unknown> = {};
            try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}: non-JSON response` }; }
            if (!r.ok) throw new Error((d.error as string) || `HTTP ${r.status}`);
            updateIdea(d);
            const ideaText = normalizeIdea(d.idea);
            if (ideaText) addMsg('assistant', ideaText);
            await fetchTree();
        } catch (err) {
            addMsg('system', `Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
        } finally {
            setLoading(false);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [draft, loading, healthy, addMsg, updateIdea, fetchTree, resetIrisSession, loadArxivPaper]);

    // ── MCTS step ──
    const handleStep = useCallback(async (action: string) => {
        if (loading || !idea) return;
        setLoading(true);
        addMsg('system', `Running: ${action.replace(/_/g, ' ')}…`);
        try {
            const r = await fetch('/api/iris/step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, use_mcts: true }),
            });
            let d: Record<string, unknown> = {};
            try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}: non-JSON response from IRIS backend` }; }
            if (!r.ok) throw new Error((d.error as string) || `HTTP ${r.status}`);
            updateIdea(d);
            const ideaText = normalizeIdea(d.idea);
            if (ideaText) addMsg('assistant', ideaText);
            await fetchTree();
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Unknown';
            addMsg('system', `Step error: ${msg}`);
            // Stop auto-generate on repeated backend errors to avoid flooding
            if (autoGenerate) {
                setAutoGenerate(false);
                addMsg('system', 'Auto-generate paused due to backend error. Click Auto to resume.');
            }
        } finally { setLoading(false); }
    }, [loading, idea, addMsg, updateIdea, fetchTree, autoGenerate]);
    // Keep the ref pointing at the latest handleStep so the interval never stales
    useEffect(() => { handleStepRef.current = handleStep; }, [handleStep]);

    // ── Judge — calls the 'judge' action which returns review_scores + review_feedback
    //    (different from 'review_and_refine' which improves the idea via MCTS) ──
    const handleJudge = useCallback(() => handleStep('judge'), [handleStep]);

    // ── Refresh ──
    const handleRefresh = useCallback(async () => {
        if (!idea || loading) return;
        setLoading(true);
        addMsg('system', 'Generating fresh research idea…');
        try {
            const r = await fetch('/api/iris/refresh-idea', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea }),
            });
            let d: Record<string, unknown> = {};
            try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}: non-JSON response` }; }
            if (!r.ok) throw new Error((d.error as string) || `HTTP ${r.status}`);
            updateIdea(d);
            const ideaText = normalizeIdea(d.idea);
            if (ideaText) addMsg('assistant', ideaText);
            await fetchTree();
        } catch (err) {
            addMsg('system', `Refresh error: ${err instanceof Error ? err.message : 'Unknown'}`);
        } finally { setLoading(false); }
    }, [idea, loading, addMsg, updateIdea, fetchTree]);

    // ── Handle review fix/ignore ──
    const handleReviewAction = useCallback(async (action: 'fix' | 'ignore') => {
        if (action === 'ignore') {
            setReviewIdx(i => Math.min(i + 1, reviewAspects.length - 1));
            return;
        }
        if (!currentAspect || currentScore === 0) return;
        setLoading(true);
        try {
            const r = await fetch('/api/iris/improve-idea', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    idea,
                    accepted_reviews: [{
                        aspect: currentAspect,
                        feedback: currentFeedbackText,
                        score: currentScore,
                    }],
                }),
            });
            let d: Record<string, unknown> = {};
            try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}: non-JSON response` }; }
            if (!r.ok) throw new Error((d.error as string) || `HTTP ${r.status}`);
            const improvedRaw = d.improved_idea || d.idea;
            updateIdea({ idea: improvedRaw, review_scores: d.review_scores as IrisReviewScores | undefined, average_score: d.average_score as number | undefined });
            const improvedText = normalizeIdea(improvedRaw);
            if (improvedText) addMsg('assistant', improvedText);
            setReviewIdx(i => Math.min(i + 1, reviewAspects.length - 1));
            await fetchTree();
        } catch (err) {
            addMsg('system', `Fix error: ${err instanceof Error ? err.message : 'Unknown'}`);
        } finally { setLoading(false); }
    }, [currentAspect, currentFeedbackText, currentScore, idea, reviewAspects.length, addMsg, updateIdea, fetchTree]);

    // ── Literature search ──
    const handleSearch = useCallback(async () => {
        const q = qaSearch.trim();
        if (!q || qaLoading) return;
        setQaLoading(true);
        try {
            const r = await fetch('/api/iris/retrieve-knowledge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: q, idea: idea || q }),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.error);
            const rawAnswer = d.knowledge || d.result || d.answer || d;
            const answer = typeof rawAnswer === 'string' ? rawAnswer : JSON.stringify(rawAnswer, null, 2);
            setQaItems(prev => [{ query: q, answer }, ...prev]);
            setQaSearch('');
        } catch (err) {
            setQaItems(prev => [{ query: q, answer: `Error: ${err instanceof Error ? err.message : 'Search failed'}` }, ...prev]);
        } finally { setQaLoading(false); }
    }, [qaSearch, qaLoading, idea]);

    // ── Retrieve knowledge into idea — delegates to /api/step retrieve_and_refine ──
    const handleRetrieveKnowledge = useCallback(async () => {
        if (!idea || loading) return;
        setLoading(true);
        addMsg('system', 'Searching literature and refining idea…');
        try {
            const r = await fetch('/api/iris/step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'retrieve_and_refine', use_mcts: true }),
            });
            let d: Record<string, unknown> = {};
            try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}: non-JSON response` }; }
            if (!r.ok) throw new Error((d.error as string) || `HTTP ${r.status}`);
            updateIdea(d as Parameters<typeof updateIdea>[0]);
            const ideaText = normalizeIdea(d.idea);
            if (ideaText) addMsg('assistant', ideaText);
            await fetchTree();
        } catch (err) {
            addMsg('system', `Retrieve error: ${err instanceof Error ? err.message : 'Unknown'}`);
        } finally { setLoading(false); }
    }, [idea, loading, addMsg, updateIdea, fetchTree]);

    // ── Reset ──
    const handleReset = useCallback(async () => {
        await resetIrisSession();
        setChatMsgs([]);
        setReviewIdx(0);
        setAutoGenerate(false);
        setShowTree(false);
        setShowHistory(false);
        setDraft('');
        setTimeout(() => inputRef.current?.focus(), 50);
    }, [resetIrisSession]);

    // ── File upload ──
    const fileInputRef = useRef<HTMLInputElement>(null);
    const handleFileUpload = useCallback(async (file: File) => {
        const form = new FormData();
        form.append('file', file);
        addMsg('system', `Uploading ${file.name}…`);
        try {
            const r = await fetch('/api/iris/upload', { method: 'POST', body: form });
            const d = await r.json();
            if (!r.ok) throw new Error(d.error);
            addMsg('system', `Attached: ${file.name}`);
        } catch (err) {
            addMsg('system', `Upload error: ${err instanceof Error ? err.message : 'Failed'}`);
        }
    }, [addMsg]);

    // ── Offline screen ──
    if (healthy === false) {
        return (
            <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc', flexDirection: 'column', gap: 12 }}>
                <WifiOff size={32} color="#ef4444" />
                <div style={{ fontSize: 16, fontWeight: 700, color: '#1e293b' }}>IRIS Service Offline</div>
                <div style={{ fontSize: 13, color: '#64748b', textAlign: 'center', lineHeight: 1.6 }}>
                    Start the backend:
                    <br />
                    <code style={{ background: '#e2e8f0', padding: '4px 10px', borderRadius: 6, fontSize: 12, display: 'inline-block', marginTop: 6 }}>
                        cd services/hypothesis-room/iris && python server_wrapper.py
                    </code>
                </div>
                <button onClick={onBack} style={{ marginTop: 8, padding: '8px 20px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                    ← Back to VREDA
                </button>
            </div>
        );
    }

    // ── Layout ──
    const col: React.CSSProperties = { display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' };
    const borderR: React.CSSProperties = { borderRight: '1px solid #e2e8f0' };
    const heading: React.CSSProperties = { fontSize: 13, fontWeight: 700, color: '#1e293b', letterSpacing: '0.04em', padding: '14px 16px 10px', flexShrink: 0, textTransform: 'uppercase' };

    return (
        <div style={{ display: 'flex', height: '100vh', background: '#f8fafc', fontFamily: "'Inter', system-ui, sans-serif", fontSize: 14, color: '#334155' }}>

            {/* ═══════════════════════════════════════════════════
                LEFT SIDEBAR — Sessions / Literature tabs
            ═══════════════════════════════════════════════════ */}
            <div style={{ width: 260, flexShrink: 0, background: '#0f172a', ...col, borderRight: '1px solid #1e293b' }}>

                {/* Brand + health */}
                <div style={{ flexShrink: 0, padding: '16px 16px 12px', borderBottom: '1px solid #1e293b' }}>
                    <div style={{ fontSize: 16, fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.02em', marginBottom: 6 }}>IRIS</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: healthy ? '#22c55e' : '#f59e0b', flexShrink: 0 }} />
                        <span style={{ color: healthy ? '#4ade80' : '#fbbf24' }}>{healthy ? 'Connected' : 'Connecting…'}</span>
                    </div>
                </div>

                {/* Tab switcher */}
                <div style={{ flexShrink: 0, display: 'flex', borderBottom: '1px solid #1e293b' }}>
                    {(['sessions', 'literature'] as const).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setLeftTab(tab)}
                            style={{
                                flex: 1, padding: '9px 0', border: 'none', cursor: 'pointer',
                                fontSize: 11, fontWeight: 600, textTransform: 'capitalize',
                                background: leftTab === tab ? '#1e293b' : 'transparent',
                                color: leftTab === tab ? '#f1f5f9' : '#64748b',
                                borderBottom: leftTab === tab ? '2px solid #3b82f6' : '2px solid transparent',
                                transition: 'all 0.15s',
                            }}
                        >{tab}</button>
                    ))}
                </div>

                {/* ── Sessions tab ── */}
                {leftTab === 'sessions' && (
                    <>
                        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '8px 0' }}>
                            {ideaHistory.length === 0 ? (
                                <div style={{ padding: '20px 16px', color: '#475569', fontSize: 12, lineHeight: 1.6 }}>
                                    No hypotheses yet.<br />Start a conversation to generate your first research idea.
                                </div>
                            ) : (
                                [...ideaHistory].reverse().map((h, ri) => {
                                    const i = ideaHistory.length - 1 - ri;
                                    const isCurrent = h.content === idea;
                                    const title = h.content.replace(/#+\s/g, '').replace(/\*\*/g, '').trim().slice(0, 60) || `Hypothesis ${i + 1}`;
                                    const timeStr = new Date(h.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                                    return (
                                        <div
                                            key={h.id}
                                            onClick={() => setHistoryModal(h)}
                                            style={{
                                                padding: '10px 14px', cursor: 'pointer', borderRadius: 0,
                                                background: isCurrent ? '#1e293b' : 'transparent',
                                                borderLeft: isCurrent ? '3px solid #3b82f6' : '3px solid transparent',
                                                transition: 'background 0.15s',
                                            }}
                                            onMouseEnter={e => { if (!isCurrent) (e.currentTarget as HTMLDivElement).style.background = '#1a2744'; }}
                                            onMouseLeave={e => { if (!isCurrent) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                                                <span style={{ fontSize: 10, fontWeight: 700, color: isCurrent ? '#93c5fd' : '#475569' }}>
                                                    v{i + 1}{isCurrent ? ' · active' : ''}
                                                </span>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                                                    {h.avgScore > 0 && (
                                                        <span style={{
                                                            fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 6,
                                                            background: h.avgScore >= 7 ? '#14532d' : h.avgScore >= 5 ? '#713f12' : '#7f1d1d',
                                                            color: h.avgScore >= 7 ? '#86efac' : h.avgScore >= 5 ? '#fde68a' : '#fca5a5',
                                                        }}>{h.avgScore.toFixed(1)}</span>
                                                    )}
                                                    <span style={{ fontSize: 9, color: '#334155' }}>{timeStr}</span>
                                                </div>
                                            </div>
                                            <div style={{ fontSize: 11.5, color: isCurrent ? '#e2e8f0' : '#94a3b8', lineHeight: 1.45, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                                                {title}
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                        {/* New session button */}
                        <div style={{ flexShrink: 0, padding: '10px 12px', borderTop: '1px solid #1e293b' }}>
                            <button
                                onClick={handleReset}
                                style={{ width: '100%', padding: '8px', borderRadius: 8, border: '1px solid #334155', background: 'transparent', color: '#94a3b8', cursor: 'pointer', fontSize: 12, fontWeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                            >
                                <RotateCcw size={13} /> New Session
                            </button>
                        </div>
                    </>
                )}

                {/* ── Literature tab ── */}
                {leftTab === 'literature' && (
                    <>
                        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', minHeight: 0 }}>
                            {qaItems.length === 0 ? (
                                <div style={{ color: '#475569', fontSize: 12, lineHeight: 1.6, padding: '12px 4px' }}>
                                    No literature queries yet. Search below to retrieve relevant papers.
                                </div>
                            ) : (
                                qaItems.map((item, i) => (
                                    <div key={i} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: '1px solid #1e293b' }}>
                                        <div style={{ fontSize: 11, fontWeight: 600, color: '#93c5fd', marginBottom: 4 }}>{item.query}</div>
                                        <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.5 }}>{item.answer.slice(0, 240)}{item.answer.length > 240 ? '…' : ''}</div>
                                    </div>
                                ))
                            )}
                        </div>
                        {/* Search + Attach */}
                        <div style={{ flexShrink: 0, padding: '10px 12px', borderTop: '1px solid #1e293b', display: 'flex', gap: 8 }}>
                            <div style={{ flex: 1, display: 'flex', alignItems: 'center', border: '1px solid #334155', borderRadius: 20, overflow: 'hidden', background: '#1e293b' }}>
                                <input
                                    value={qaSearch}
                                    onChange={e => setQaSearch(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                                    placeholder="Search literature..."
                                    style={{ flex: 1, padding: '7px 12px', border: 'none', outline: 'none', fontSize: 12, background: 'transparent', color: '#f1f5f9' }}
                                />
                                <button
                                    onClick={handleSearch}
                                    disabled={qaLoading || !qaSearch.trim()}
                                    style={{ padding: '7px 10px', background: '#334155', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', color: '#94a3b8' }}
                                >
                                    {qaLoading ? <RefreshCw size={14} style={{ animation: 'iris-spin 1s linear infinite' }} /> : <Search size={14} />}
                                </button>
                            </div>
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                title="Attach PDF / document"
                                style={{ width: 34, height: 34, borderRadius: 20, background: '#1e293b', border: '1px solid #334155', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: '#94a3b8' }}
                            >
                                <Paperclip size={14} />
                            </button>
                            <input ref={fileInputRef} type="file" accept=".txt,.pdf,.doc,.docx" style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f); e.target.value = ''; }} />
                        </div>
                    </>
                )}
            </div>

            {/* ═══════════════════════════════════════════════════
                CENTER — Chat + Toolbar
            ═══════════════════════════════════════════════════ */}
            <div style={{ flex: 1, minWidth: 0, background: '#ffffff', ...borderR, ...col }}>

                {/* Top toolbar */}
                <div style={{
                    flexShrink: 0, padding: '8px 12px',
                    borderBottom: '1px solid #e2e8f0',
                    display: 'flex', alignItems: 'center', gap: 6,
                }}>
                    {/* Back */}
                    <button onClick={onBack} title="Back to VREDA" style={toolbarBtn()}>
                        <ArrowLeft size={15} />
                        <span style={{ fontSize: 11, fontWeight: 600 }}>VREDA</span>
                    </button>

                    <div style={{ width: 1, height: 20, background: '#e2e8f0', margin: '0 4px' }} />

                    {/* Auto-generate */}
                    <button
                        onClick={() => setAutoGenerate(a => !a)}
                        title="Auto-generate"
                        style={toolbarBtn(autoGenerate)}
                    >
                        <Zap size={14} fill={autoGenerate ? '#3b82f6' : 'none'} />
                        <span style={{ fontSize: 11 }}>Auto</span>
                    </button>

                    {/* MCTS actions */}
                    <button onClick={() => handleStep('generate')} disabled={!idea || loading} style={toolbarBtn()} title="Generate next idea">
                        <ChevronRight size={15} />
                        <span style={{ fontSize: 11 }}>Generate</span>
                    </button>
                    <button onClick={() => handleStep('retrieve_and_refine')} disabled={!idea || loading} style={toolbarBtn()} title="Retrieve & Refine">
                        <BookOpen size={14} />
                        <span style={{ fontSize: 11 }}>Retrieve</span>
                    </button>

                    {/* Judge */}
                    <button onClick={handleJudge} disabled={!idea || loading} style={toolbarBtn()} title="Review & Refine">
                        <Star size={14} />
                        <span style={{ fontSize: 11 }}>Judge</span>
                    </button>

                    {/* History toggle */}
                    {ideaHistory.length > 0 && (
                        <button onClick={() => setShowHistory(h => !h)} style={toolbarBtn(showHistory)} title="Hypothesis history">
                            <span style={{ fontSize: 13 }}>📋</span>
                            <span style={{ fontSize: 11 }}>History ({ideaHistory.length})</span>
                        </button>
                    )}

                    {/* Tree toggle */}
                    <button onClick={() => setShowTree(t => !t)} style={toolbarBtn(showTree)} title="Toggle MCTS Tree">
                        <span style={{ fontSize: 13 }}>🌳</span>
                        <span style={{ fontSize: 11 }}>Tree</span>
                    </button>

                    {/* Reset */}
                    <button onClick={handleReset} style={{ ...toolbarBtn(), marginLeft: 'auto' }} title="New session">
                        <RotateCcw size={13} />
                        <span style={{ fontSize: 11 }}>Reset</span>
                    </button>
                </div>

                {/* Proposal box (sticky) */}
                {idea && (
                    <div style={{
                        flexShrink: 0,
                        background: '#f8fafc', border: '1px solid #e2e8f0',
                        borderRadius: 8, margin: '10px 16px 0',
                        padding: '10px 14px',
                        position: 'relative',
                        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Current Research Proposal</div>
                            {paperTitle && (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, background: '#eef2ff', color: '#4338ca', border: '1px solid #c7d2fe', borderRadius: 10, padding: '1px 7px', fontWeight: 500 }}>
                                    <FileText size={10} /> {paperTitle}
                                </span>
                            )}
                        </div>
                        <div style={{ fontSize: 13, color: '#1e293b', lineHeight: 1.55, maxHeight: 80, overflow: 'hidden', maskImage: 'linear-gradient(to bottom, black 70%, transparent 100%)' }}>
                            {idea}
                        </div>
                    </div>
                )}

                {/* Hypothesis History Panel */}
                {showHistory && ideaHistory.length > 0 && (
                    <div style={{ flexShrink: 0, background: '#f8fafc', borderTop: '1px solid #e2e8f0', borderBottom: '1px solid #e2e8f0', padding: '10px 16px', maxHeight: 260, overflowY: 'auto' }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
                            Hypothesis History — {ideaHistory.length} version{ideaHistory.length !== 1 ? 's' : ''}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {ideaHistory.map((h, i) => {
                                const isCurrent = h.content === idea;
                                return (
                                    <div
                                        key={h.id}
                                        onClick={() => setHistoryModal(h)}
                                        style={{
                                            padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                                            background: isCurrent ? '#eff6ff' : '#ffffff',
                                            border: `1px solid ${isCurrent ? '#bfdbfe' : '#e5e7eb'}`,
                                            transition: 'background 0.15s',
                                        }}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                                            <span style={{ fontSize: 10, fontWeight: 700, color: isCurrent ? '#2563eb' : '#6b7280' }}>
                                                v{i + 1}{isCurrent ? ' · current' : ''}
                                            </span>
                                            {h.avgScore > 0 && (
                                                <span style={{
                                                    fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 8,
                                                    background: h.avgScore >= 7 ? '#dcfce7' : h.avgScore >= 5 ? '#fef9c3' : '#fee2e2',
                                                    color: h.avgScore >= 7 ? '#166534' : h.avgScore >= 5 ? '#854d0e' : '#991b1b',
                                                }}>{h.avgScore.toFixed(1)}/10</span>
                                            )}
                                        </div>
                                        <div style={{ fontSize: 11, color: '#374151', lineHeight: 1.45, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                                            {h.content.replace(/#+\s/g, '').replace(/\*\*/g, '').slice(0, 150)}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Chat messages */}
                <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 0 }}>

                    {!hasStarted && (
                        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'flex-start', color: '#94a3b8', fontSize: 14 }}>
                            Welcome to IRIS.
                        </div>
                    )}

                    {/* MCTS tree panel */}
                    {showTree && treeData && (
                        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 10, fontSize: 11, color: '#475569' }}>
                            <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 12 }}>MCTS Tree</div>
                            <TreeNode node={treeData} depth={0} />
                        </div>
                    )}

                    {chatMsgs.map((m, i) => (
                        <div key={i} data-sender={m.role} style={msgStyle(m.role)}>
                            {m.role === 'user' && <span style={{ fontWeight: 600, fontSize: 12, color: '#374151' }}>You: </span>}
                            {m.role === 'assistant'
                                ? <IdeaRenderer text={m.content} />
                                : <span style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6 }}>{m.content}</span>
                            }
                        </div>
                    ))}

                    {loading && (
                        <div style={msgStyle('system')}>
                            IRIS is thinking <TypingDots />
                        </div>
                    )}

                    <div ref={chatEndRef} />
                </div>

                {/* Input bar */}
                <div style={{ flexShrink: 0, display: 'flex', gap: 8, padding: '10px 14px', borderTop: '1px solid #e2e8f0', background: '#ffffff' }}>
                    <input
                        ref={inputRef}
                        value={draft}
                        onChange={e => setDraft(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                        placeholder={inputPlaceholder}
                        disabled={loading || !healthy}
                        autoFocus
                        style={{
                            flex: 1, padding: '9px 14px',
                            border: '1px solid #e2e8f0', borderRadius: 24,
                            fontSize: 13, color: '#1e293b',
                            background: '#f8fafc', outline: 'none',
                        }}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!draft.trim() || loading || !healthy}
                        style={{
                            padding: '9px 18px', borderRadius: 24,
                            background: draft.trim() && !loading ? '#3b82f6' : '#e2e8f0',
                            color: draft.trim() && !loading ? '#fff' : '#94a3b8',
                            border: 'none', cursor: draft.trim() ? 'pointer' : 'default',
                            fontSize: 13, fontWeight: 600, transition: 'background 0.15s',
                        }}
                    >
                        Send
                    </button>
                </div>
            </div>

            {/* ═══════════════════════════════════════════════════
                RIGHT SIDEBAR — Research Brief
            ═══════════════════════════════════════════════════ */}
            <div style={{ width: 300, flexShrink: 0, background: '#ffffff', ...col }}>
                <div style={heading}>Research Brief</div>

                {/* Overall score */}
                <div style={{ padding: '0 16px 6px', flexShrink: 0 }}>
                    <Score value={avgScore} />
                </div>

                {/* Per-dimension score bars */}
                {Object.keys(reviewScores).length > 0 && (
                    <div style={{ padding: '0 16px 10px', flexShrink: 0 }}>
                        {(Object.entries(reviewScores) as [string, number][]).map(([aspect, score]) => (
                            <div key={aspect} style={{ marginBottom: 5 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#64748b', marginBottom: 2 }}>
                                    <span style={{ textTransform: 'capitalize' }}>{aspect}</span>
                                    <span style={{ fontWeight: 600, color: score >= 7 ? '#166534' : score >= 5 ? '#854d0e' : '#991b1b' }}>{score.toFixed(1)}</span>
                                </div>
                                <div style={{ height: 4, background: '#e2e8f0', borderRadius: 2 }}>
                                    <div style={{ height: '100%', width: `${(score / 10) * 100}%`, background: score >= 7 ? '#22c55e' : score >= 5 ? '#f59e0b' : '#ef4444', borderRadius: 2, transition: 'width 0.4s ease' }} />
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Idea content — rendered as formatted sections */}
                <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '0 16px 16px' }}>
                    {!idea ? (
                        <div style={{ color: '#94a3b8', fontSize: 12, lineHeight: 1.65 }}>
                            Your evolving research brief will appear here. Start by entering your initial research idea in the chat.
                        </div>
                    ) : (
                        <IdeaRenderer text={idea} />
                    )}
                </div>

                {/* Review feedback bar */}
                {idea && reviewAspects.length > 0 && (currentScore > 0 || currentFeedbackText) && (
                    <div style={{
                        flexShrink: 0, padding: '12px 16px',
                        background: '#fff', borderTop: '1px solid #e5e7eb',
                        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10,
                    }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                                <div style={{ fontSize: 10, fontWeight: 700, color: '#6b7280', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                                    {currentAspect.replace(/_/g, ' ')}
                                </div>
                                {currentScore > 0 && (
                                    <span style={{
                                        fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 8,
                                        background: currentScore >= 7 ? '#dcfce7' : currentScore >= 5 ? '#fef9c3' : '#fee2e2',
                                        color: currentScore >= 7 ? '#166534' : currentScore >= 5 ? '#854d0e' : '#991b1b',
                                    }}>{currentScore.toFixed(1)}/10</span>
                                )}
                            </div>
                            <div style={{ fontSize: 11, color: '#374151', lineHeight: 1.5, maxHeight: 72, overflow: 'hidden' }}>
                                {currentFeedbackText.slice(0, 200) || 'Click "Generate Review" to see detailed feedback.'}
                            </div>
                            <div style={{ display: 'flex', gap: 8, marginTop: 6, alignItems: 'center' }}>
                                <button onClick={() => setReviewIdx(i => Math.max(0, i - 1))} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 11, color: '#6b7280', padding: 0 }}>← Prev</button>
                                <span style={{ fontSize: 10, color: '#94a3b8' }}>{reviewIdx + 1}/{reviewAspects.length}</span>
                                <button onClick={() => setReviewIdx(i => Math.min(i + 1, reviewAspects.length - 1))} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 11, color: '#6b7280', padding: 0 }}>Next →</button>
                            </div>
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                            <button
                                onClick={() => handleReviewAction('fix')}
                                disabled={loading}
                                title="Fix this issue"
                                style={{ width: 36, height: 36, borderRadius: 8, background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            >✓</button>
                            <button
                                onClick={() => handleReviewAction('ignore')}
                                title="Ignore"
                                style={{ width: 36, height: 36, borderRadius: 8, background: '#e5e7eb', color: '#374151', border: 'none', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            >✕</button>
                        </div>
                    </div>
                )}

                {/* Action buttons */}
                {idea && (
                    <div style={{ flexShrink: 0, padding: '10px 12px', borderTop: '1px solid #e5e7eb', display: 'flex', gap: 8 }}>
                        <button
                            onClick={handleJudge}
                            disabled={loading}
                            style={actionBtn('#3b82f6', '#fff')}
                        >
                            <Star size={13} /> Generate Review
                        </button>
                        <button
                            onClick={handleRetrieveKnowledge}
                            disabled={loading}
                            style={actionBtn('#f1f5f9', '#475569')}
                        >
                            <BookOpen size={13} /> Retrieve
                        </button>
                        <button
                            onClick={handleRefresh}
                            disabled={loading}
                            title="Refresh idea"
                            style={{ width: 34, height: 34, borderRadius: 8, background: '#f1f5f9', border: '1px solid #e2e8f0', cursor: loading ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}
                        >
                            <RefreshCw size={13} style={loading ? { animation: 'iris-spin 1s linear infinite' } : {}} />
                        </button>
                    </div>
                )}
            </div>

            <style>{`
                @keyframes iris-spin { to { transform: rotate(360deg); } }
            `}</style>

            {/* ── Hypothesis History Modal ── */}
            {historyModal && (
                <div
                    onClick={() => setHistoryModal(null)}
                    style={{
                        position: 'fixed', inset: 0, zIndex: 1000,
                        background: 'rgba(15, 23, 42, 0.55)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                >
                    <div
                        onClick={e => e.stopPropagation()}
                        style={{
                            width: 680, maxWidth: '92vw', maxHeight: '82vh',
                            background: '#fff', borderRadius: 14,
                            boxShadow: '0 20px 60px rgba(0,0,0,0.22)',
                            display: 'flex', flexDirection: 'column', overflow: 'hidden',
                        }}
                    >
                        {/* Header */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid #e2e8f0', flexShrink: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <span style={{ fontSize: 13, fontWeight: 700, color: '#1e293b' }}>
                                    {historyModal.id.toUpperCase()} — Hypothesis Detail
                                </span>
                                {historyModal.avgScore > 0 && (
                                    <span style={{
                                        fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
                                        background: historyModal.avgScore >= 7 ? '#dcfce7' : historyModal.avgScore >= 5 ? '#fef9c3' : '#fee2e2',
                                        color: historyModal.avgScore >= 7 ? '#166534' : historyModal.avgScore >= 5 ? '#854d0e' : '#991b1b',
                                    }}>Score: {historyModal.avgScore.toFixed(1)}/10</span>
                                )}
                            </div>
                            <button onClick={() => setHistoryModal(null)} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 18, color: '#6b7280', lineHeight: 1 }}>✕</button>
                        </div>

                        {/* Scores bar */}
                        {Object.keys(historyModal.scores).length > 0 && (
                            <div style={{ display: 'flex', gap: 8, padding: '10px 18px', flexShrink: 0, borderBottom: '1px solid #f1f5f9', flexWrap: 'wrap' }}>
                                {(Object.entries(historyModal.scores) as [string, number][]).map(([aspect, score]) => (
                                    <div key={aspect} style={{ minWidth: 90, flex: '1 1 90px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#64748b', marginBottom: 2, textTransform: 'capitalize' }}>
                                            <span>{aspect}</span>
                                            <span style={{ fontWeight: 700, color: score >= 7 ? '#166534' : score >= 5 ? '#854d0e' : '#991b1b' }}>{score.toFixed(1)}</span>
                                        </div>
                                        <div style={{ height: 4, background: '#e2e8f0', borderRadius: 2 }}>
                                            <div style={{ height: '100%', width: `${(score / 10) * 100}%`, background: score >= 7 ? '#22c55e' : score >= 5 ? '#f59e0b' : '#ef4444', borderRadius: 2 }} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Full content */}
                        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 18px', minHeight: 0 }}>
                            <IdeaRenderer text={historyModal.content} />
                        </div>

                        {/* Footer actions */}
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '12px 18px', borderTop: '1px solid #e2e8f0', flexShrink: 0, background: '#f8fafc' }}>
                            <button
                                onClick={() => setHistoryModal(null)}
                                style={{ padding: '7px 16px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', color: '#374151', cursor: 'pointer', fontSize: 12, fontWeight: 500 }}
                            >Close</button>
                            <button
                                onClick={() => { setIdea(historyModal.content); setHistoryModal(null); }}
                                style={{ padding: '7px 16px', borderRadius: 8, border: 'none', background: '#3b82f6', color: '#fff', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
                            >Restore this version</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Helpers ──
// ── IdeaRenderer — renders hypothesis markdown as clean formatted sections ──
function IdeaRenderer({ text }: { text: string }) {
    if (!text) return null;
    // Split on markdown headings (# ## ###)
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let currentSection: string[] = [];
    let currentHeading = '';
    let currentLevel = 0;
    let key = 0;

    const flushSection = () => {
        if (!currentSection.length && !currentHeading) return;
        const body = currentSection.join('\n').trim();
        if (currentHeading) {
            const Tag = currentLevel === 1 ? 'h2' : 'h3';
            const headingStyle: React.CSSProperties = currentLevel === 1
                ? { margin: '18px 0 8px', fontSize: 14, fontWeight: 700, color: '#1e293b', borderBottom: '2px solid #e2e8f0', paddingBottom: 5 }
                : { margin: '14px 0 6px', fontSize: 13, fontWeight: 700, color: '#334155' };
            elements.push(<Tag key={key++} style={headingStyle}>{currentHeading}</Tag>);
        }
        if (body) {
            // Render body — handle bullet lists and bold
            const rendered = body.split('\n').map((line, i) => {
                const trimmed = line.trim();
                if (!trimmed) return <br key={i} />;
                // Bullet
                if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                    return (
                        <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 3, paddingLeft: 8 }}>
                            <span style={{ color: '#3b82f6', flexShrink: 0, marginTop: 2 }}>•</span>
                            <span style={{ fontSize: 12.5, color: '#374151', lineHeight: 1.65 }} dangerouslySetInnerHTML={{ __html: trimmed.slice(2).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
                        </div>
                    );
                }
                // Numbered
                const numMatch = trimmed.match(/^(\d+)\.\s+(.+)/);
                if (numMatch) {
                    return (
                        <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4, paddingLeft: 8 }}>
                            <span style={{ color: '#6366f1', fontWeight: 700, flexShrink: 0, fontSize: 12, minWidth: 18 }}>{numMatch[1]}.</span>
                            <span style={{ fontSize: 12.5, color: '#374151', lineHeight: 1.65 }} dangerouslySetInnerHTML={{ __html: numMatch[2].replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
                        </div>
                    );
                }
                // Paragraph
                return <p key={i} style={{ margin: '0 0 6px', fontSize: 12.5, color: '#374151', lineHeight: 1.7 }} dangerouslySetInnerHTML={{ __html: trimmed.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />;
            });
            elements.push(<div key={key++}>{rendered}</div>);
        }
        currentSection = [];
        currentHeading = '';
    };

    for (const line of lines) {
        const h1 = line.match(/^#\s+(.+)/);
        const h2 = line.match(/^##\s+(.+)/);
        const h3 = line.match(/^###\s+(.+)/);
        if (h1) {
            flushSection();
            currentHeading = h1[1]; currentLevel = 1;
        } else if (h2) {
            flushSection();
            currentHeading = h2[1]; currentLevel = 2;
        } else if (h3) {
            flushSection();
            currentHeading = h3[1]; currentLevel = 3;
        } else {
            currentSection.push(line);
        }
    }
    flushSection();

    return <div style={{ paddingTop: 4 }}>{elements}</div>;
}

function toolbarBtn(active = false): React.CSSProperties {
    return {
        display: 'flex', alignItems: 'center', gap: 4,
        padding: '5px 10px', borderRadius: 8,
        border: active ? '1px solid #bfdbfe' : '1px solid #e2e8f0',
        background: active ? '#eff6ff' : '#f8fafc',
        color: active ? '#2563eb' : '#475569',
        cursor: 'pointer', fontSize: 12, fontWeight: 500,
        transition: 'all 0.15s',
    };
}

function actionBtn(bg: string, color: string): React.CSSProperties {
    return {
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        padding: '6px 8px', borderRadius: 8,
        background: bg, color, border: 'none',
        cursor: 'pointer', fontSize: 11, fontWeight: 600,
    };
}

function msgStyle(role: ChatMsg['role']): React.CSSProperties {
    return {
        padding: role === 'system' ? '4px 0' : '6px 0',
        borderBottom: role !== 'system' ? '1px solid #f1f5f9' : 'none',
        fontSize: 13,
        color: role === 'system' ? '#94a3b8' : '#334155',
        fontStyle: role === 'system' ? 'italic' : undefined,
    };
}

// ── Inline tree renderer ──
function TreeNode({ node, depth }: { node: IrisMCTSTreeNode; depth: number }) {
    const [open, setOpen] = useState(depth < 2);
    const hasChildren = node.children && node.children.length > 0;
    return (
        <div style={{ paddingLeft: depth * 12 }}>
            <div
                onClick={() => hasChildren && setOpen(o => !o)}
                style={{ cursor: hasChildren ? 'pointer' : 'default', padding: '2px 0', display: 'flex', alignItems: 'center', gap: 4 }}
            >
                {hasChildren ? (open ? '▾' : '▸') : '·'}
                <span style={{ fontSize: 11, color: '#374151' }}>
                    {node.action ?? 'root'} {node.value != null ? `(${node.value.toFixed(2)})` : ''}
                </span>
            </div>
            {open && hasChildren && node.children!.map((c, i) => (
                <TreeNode key={i} node={c} depth={depth + 1} />
            ))}
        </div>
    );
}
