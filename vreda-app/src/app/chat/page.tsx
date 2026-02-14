'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/chat/Sidebar';
import ChatArea from '@/components/chat/ChatArea';
import ChatInput from '@/components/chat/ChatInput';
import type { Message, PipelineProgressEvent } from '@/types';
import type { StrategistPhase, PaperAnalysis, CodePathAssessment } from '@/types/strategist';
import type { PaperMetadata } from '@/lib/literature/types';
import { FlaskConical } from 'lucide-react';

/** Read an NDJSON stream and update a progress message in-place. */
async function consumeNDJSONStream(
    response: Response,
    progressMsgId: string,
    setMessages: React.Dispatch<React.SetStateAction<Message[]>>
): Promise<{ completeData: Record<string, unknown> | null; errorMessage: string | null }> {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let completeData: Record<string, unknown> | null = null;
    let errorMessage: string | null = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const event: PipelineProgressEvent = JSON.parse(line);
                if (event.type === 'progress' || event.type === 'warning') {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === progressMsgId
                                ? {
                                    ...m,
                                    metadata: {
                                        ...m.metadata,
                                        pipeline_events: [
                                            ...(m.metadata?.pipeline_events || []),
                                            event,
                                        ],
                                    },
                                }
                                : m
                        )
                    );
                } else if (event.type === 'complete') {
                    completeData = (event as PipelineProgressEvent & { data?: Record<string, unknown> }).data || null;
                } else if (event.type === 'error') {
                    errorMessage = event.message;
                }
            } catch {
                // Skip malformed lines
            }
        }
    }

    return { completeData, errorMessage };
}

export default function ChatPage() {
    const [userId, setUserId] = useState<string | null>(null);
    const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [streamingText, setStreamingText] = useState('');
    const [strategistSessionId, setStrategistSessionId] = useState<string | null>(null);
    const [strategistPhase, setStrategistPhase] = useState<StrategistPhase>('idle');
    const [strategistLoading, setStrategistLoading] = useState(false);
    const [importingPaper, setImportingPaper] = useState<string | null>(null);
    // Ref to skip the fetchMessages useEffect when we just created a conversation
    // for a pipeline operation (fetch/upload). Without this, the useEffect fires
    // because activeConversationId changed, fetches 0 messages from DB, and wipes
    // the locally-added progress card — a race condition.
    const skipNextFetchRef = useRef(false);
    const supabase = createClient();
    const router = useRouter();

    // Get current user
    useEffect(() => {
        const getUser = async () => {
            const {
                data: { user },
            } = await supabase.auth.getUser();
            if (!user) {
                router.push('/auth/login');
                return;
            }
            setUserId(user.id);
        };
        getUser();
    }, []);

    // Fetch messages when conversation changes
    useEffect(() => {
        if (!activeConversationId) {
            setMessages([]);
            return;
        }
        // Skip if we just created this conversation for a pipeline operation.
        // The pipeline builds messages locally via NDJSON stream — fetching from
        // DB here would overwrite them with an empty array (race condition).
        if (skipNextFetchRef.current) {
            skipNextFetchRef.current = false;
            return;
        }
        fetchMessages(activeConversationId);
    }, [activeConversationId]);

    const fetchMessages = async (conversationId: string) => {
        const res = await fetch(`/api/conversations/${conversationId}/messages`);
        if (res.ok) {
            const data = await res.json();
            setMessages(data);
        }
    };

    const createNewConversation = useCallback(async () => {
        const res = await fetch('/api/conversations', { method: 'POST' });
        if (res.ok) {
            const conv = await res.json();
            setActiveConversationId(conv.id);
            setMessages([]);
        }
    }, []);

    const handleSendMessage = useCallback(
        async (text: string) => {
            if (!userId) return;

            let convId = activeConversationId;

            // Auto-create conversation if none active
            if (!convId) {
                const res = await fetch('/api/conversations', { method: 'POST' });
                if (res.ok) {
                    const conv = await res.json();
                    convId = conv.id;
                    skipNextFetchRef.current = true;
                    setActiveConversationId(conv.id);
                } else {
                    return;
                }
            }

            // Add user message to UI immediately
            const userMsg: Message = {
                id: crypto.randomUUID(),
                conversation_id: convId!,
                role: 'user',
                content: text,
                metadata: { type: 'text' },
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, userMsg]);
            setIsLoading(true);
            setStreamingText('');

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: text,
                        conversation_id: convId,
                        user_id: userId,
                    }),
                });

                if (!res.ok) {
                    // Try to get error details from response
                    let errorText = 'Chat request failed';
                    try {
                        const errData = await res.json();
                        errorText = errData.error || errorText;
                    } catch {
                        // Response might not be JSON
                    }
                    throw new Error(errorText);
                }

                // Stream the response
                const reader = res.body?.getReader();
                const decoder = new TextDecoder();
                let fullText = '';

                if (reader) {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        const chunk = decoder.decode(value, { stream: true });
                        fullText += chunk;
                        setStreamingText(fullText);
                    }
                }

                // Add final assistant message
                const aiMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: convId!,
                    role: 'assistant',
                    content: fullText,
                    metadata: { type: 'text' },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, aiMsg]);
                setStreamingText('');
            } catch (error) {
                console.error('Send message error:', error);
                const errMsg = error instanceof Error ? error.message : 'Something went wrong';
                const errorMessage: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: convId!,
                    role: 'assistant',
                    content: errMsg.includes('rate') || errMsg.includes('quota') || errMsg.includes('429')
                        ? '⚠️ **Gemini API Rate Limit** — Your free-tier quota was exceeded. Please wait ~60 seconds and try again.'
                        : `⚠️ ${errMsg}`,
                    metadata: { type: 'error' },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, errorMessage]);
            } finally {
                setIsLoading(false);
            }
        },
        [userId, activeConversationId]
    );

    const handleUploadFile = useCallback(
        async (file: File) => {
            if (!userId) return;

            let convId = activeConversationId;

            // Auto-create conversation if none active
            if (!convId) {
                const res = await fetch('/api/conversations', { method: 'POST' });
                if (res.ok) {
                    const conv = await res.json();
                    convId = conv.id;
                    skipNextFetchRef.current = true;
                    setActiveConversationId(conv.id);
                } else {
                    return;
                }
            }

            // Validate file size (50MB max)
            const maxSize = 50 * 1024 * 1024;
            if (file.size > maxSize) {
                const errorMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: convId!,
                    role: 'assistant',
                    content: `**Upload Error:** File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum size is 50MB.`,
                    metadata: { type: 'error' },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, errorMsg]);
                return;
            }

            // Show upload message in UI
            const uploadMsg: Message = {
                id: crypto.randomUUID(),
                conversation_id: convId!,
                role: 'user',
                content: `Uploaded: **${file.name}**`,
                metadata: { type: 'pdf_upload', filename: file.name },
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, uploadMsg]);
            setIsProcessing(true);

            // Add progress message (will be updated in-place)
            const progressMsgId = crypto.randomUUID();
            const progressMsg: Message = {
                id: progressMsgId,
                conversation_id: convId!,
                role: 'assistant',
                content: `Processing **${file.name}**...`,
                metadata: {
                    type: 'pipeline_progress',
                    pipeline_events: [],
                    pipeline_title: `Processing ${file.name}`,
                },
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, progressMsg]);

            try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('conversation_id', convId!);
                formData.append('user_id', userId);

                const res = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData,
                });

                // Check if it's NDJSON stream or JSON error
                const contentType = res.headers.get('content-type') || '';
                if (contentType.includes('ndjson') && res.body) {
                    const { completeData, errorMessage } = await consumeNDJSONStream(
                        res, progressMsgId, setMessages
                    );

                    if (errorMessage) {
                        setMessages((prev) =>
                            prev.map((m) =>
                                m.id === progressMsgId
                                    ? { ...m, content: `**Upload Error:** ${errorMessage}`, metadata: { type: 'error' } as const }
                                    : m
                            )
                        );
                    } else if (completeData) {
                        const data = completeData as {
                            session_id?: string; document_id?: string;
                            paper_analysis?: PaperAnalysis;
                            code_path?: CodePathAssessment;
                            chunks_count?: number; chunks_embedded?: number; chunks_failed?: number;
                        };

                        if (data.session_id) {
                            setStrategistSessionId(data.session_id);
                            setStrategistPhase('analysis_complete');
                        }

                        if (data.paper_analysis) {
                            setMessages((prev) =>
                                prev.map((m) =>
                                    m.id === progressMsgId
                                        ? {
                                            ...m,
                                            content: `**Paper analyzed!** Found ${data.chunks_count} text chunks.${
                                                data.chunks_failed ? ` (${data.chunks_embedded} of ${(data.chunks_embedded || 0) + (data.chunks_failed || 0)} embedded)` : ''
                                            }\n\nYou can discuss the paper, or ask me to **brainstorm hypotheses**.`,
                                            metadata: {
                                                type: 'paper_analysis' as const,
                                                document_id: data.document_id,
                                                session_id: data.session_id,
                                                paper_analysis: data.paper_analysis,
                                                code_path: data.code_path,
                                            },
                                        }
                                        : m
                                )
                            );
                        } else {
                            setMessages((prev) =>
                                prev.map((m) =>
                                    m.id === progressMsgId
                                        ? { ...m, content: `**Paper processed!** ${data.chunks_count} chunks embedded. You can now ask questions about the paper.`, metadata: { type: 'text' as const } }
                                        : m
                                )
                            );
                        }
                    }
                } else {
                    // JSON error response (validation, auth)
                    const data = await res.json();
                    throw new Error(data.error || 'Upload failed');
                }
            } catch (error) {
                const errText = error instanceof Error
                    ? (error.name === 'AbortError' ? 'Upload timed out. Please try again.' : error.message)
                    : 'Something went wrong.';
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === progressMsgId
                            ? { ...m, content: `**Upload Error:** ${errText}`, metadata: { type: 'error' } }
                            : m
                    )
                );
            } finally {
                setIsProcessing(false);
            }
        },
        [userId, activeConversationId]
    );

    // ---- Strategist Action Handlers ----

    const handleSelectHypothesis = useCallback(
        async (hypothesisId: string) => {
            if (!strategistSessionId || !activeConversationId) return;

            setStrategistLoading(true);
            try {
                const res = await fetch('/api/strategist/budget', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: strategistSessionId,
                        hypothesis_id: hypothesisId,
                    }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error || 'Budget estimation failed');
                }

                const data = await res.json();
                setStrategistPhase(data.phase);

                const budgetMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: activeConversationId,
                    role: 'assistant',
                    content: `Here's the budget estimate for your selected hypothesis. Review the costs and click **Approve** when ready.`,
                    metadata: {
                        type: 'budget_quote',
                        session_id: strategistSessionId,
                        budget_quote: data.budget,
                    },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, budgetMsg]);
            } catch (error) {
                const errText = error instanceof Error ? error.message : 'Something went wrong';
                const errorMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: activeConversationId,
                    role: 'assistant',
                    content: `**Budget Error:** ${errText}`,
                    metadata: { type: 'error' },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, errorMsg]);
            } finally {
                setStrategistLoading(false);
            }
        },
        [strategistSessionId, activeConversationId]
    );

    const handleRefineHypotheses = useCallback(
        async (message: string) => {
            if (!strategistSessionId || !activeConversationId) return;

            // Show user refinement message
            const userMsg: Message = {
                id: crypto.randomUUID(),
                conversation_id: activeConversationId,
                role: 'user',
                content: message,
                metadata: { type: 'text' },
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, userMsg]);
            setStrategistLoading(true);

            try {
                const res = await fetch('/api/strategist/hypothesize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: strategistSessionId,
                        message,
                    }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error || 'Hypothesis generation failed');
                }

                const data = await res.json();
                setStrategistPhase(data.phase);

                const hypothesisMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: activeConversationId,
                    role: 'assistant',
                    content: `Here are your refined hypotheses. Select one to get a budget estimate, or refine further.`,
                    metadata: {
                        type: 'hypothesis_options',
                        session_id: strategistSessionId,
                        brainstormer_output: data.brainstormer_output,
                    },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, hypothesisMsg]);
            } catch (error) {
                const errText = error instanceof Error ? error.message : 'Something went wrong';
                const errorMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: activeConversationId,
                    role: 'assistant',
                    content: `**Hypothesis Error:** ${errText}`,
                    metadata: { type: 'error' },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, errorMsg]);
            } finally {
                setStrategistLoading(false);
            }
        },
        [strategistSessionId, activeConversationId]
    );

    const handleApproveBudget = useCallback(
        async () => {
            if (!strategistSessionId || !activeConversationId) return;

            setStrategistLoading(true);
            try {
                const res = await fetch('/api/strategist/approve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: strategistSessionId }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error || 'Approval failed');
                }

                const data = await res.json();
                setStrategistPhase(data.phase);

                const approvalMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: activeConversationId,
                    role: 'assistant',
                    content: `**Research Manifest Approved!** Your Enhanced Research Manifest is ready. The experiment can now be executed based on the hypothesis: **"${data.manifest.hypothesis.title}"**`,
                    metadata: {
                        type: 'enhanced_manifest',
                        session_id: strategistSessionId,
                        enhanced_manifest: data.manifest,
                    },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, approvalMsg]);
            } catch (error) {
                const errText = error instanceof Error ? error.message : 'Something went wrong';
                const errorMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: activeConversationId,
                    role: 'assistant',
                    content: `**Approval Error:** ${errText}`,
                    metadata: { type: 'error' },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, errorMsg]);
            } finally {
                setStrategistLoading(false);
            }
        },
        [strategistSessionId, activeConversationId]
    );

    // ---- Literature Handlers ----

    const handleFetchArxiv = useCallback(
        async (arxivId: string) => {
            if (!userId) return;

            let convId = activeConversationId;

            if (!convId) {
                const res = await fetch('/api/conversations', { method: 'POST' });
                if (res.ok) {
                    const conv = await res.json();
                    convId = conv.id;
                    skipNextFetchRef.current = true;
                    setActiveConversationId(conv.id);
                } else {
                    return;
                }
            }

            const userMsg: Message = {
                id: crypto.randomUUID(),
                conversation_id: convId!,
                role: 'user',
                content: `Fetch paper from arXiv: **${arxivId}**`,
                metadata: { type: 'text' },
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, userMsg]);
            setIsProcessing(true);

            // Add progress message (updated in-place via NDJSON stream)
            const progressMsgId = crypto.randomUUID();
            const progressMsg: Message = {
                id: progressMsgId,
                conversation_id: convId!,
                role: 'assistant',
                content: `Fetching **arXiv:${arxivId}**...`,
                metadata: {
                    type: 'pipeline_progress',
                    pipeline_events: [],
                    pipeline_title: `Fetching arXiv:${arxivId}`,
                },
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, progressMsg]);

            try {
                const res = await fetch('/api/literature/fetch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        arxiv_id: arxivId,
                        conversation_id: convId,
                    }),
                });

                // Check if it's NDJSON stream or JSON error
                const contentType = res.headers.get('content-type') || '';
                if (contentType.includes('ndjson') && res.body) {
                    const { completeData, errorMessage } = await consumeNDJSONStream(
                        res, progressMsgId, setMessages
                    );

                    if (errorMessage) {
                        setMessages((prev) =>
                            prev.map((m) =>
                                m.id === progressMsgId
                                    ? { ...m, content: `**Fetch Error:** ${errorMessage}`, metadata: { type: 'error' as const } }
                                    : m
                            )
                        );
                    } else if (completeData) {
                        const data = completeData as {
                            session_id?: string; document_id?: string;
                            paper?: { title?: string };
                            paper_analysis?: PaperAnalysis;
                            code_path?: CodePathAssessment;
                            chunks_embedded?: number; chunks_failed?: number;
                        };

                        if (data.session_id) {
                            setStrategistSessionId(data.session_id);
                            setStrategistPhase('analysis_complete');
                        }

                        if (data.paper_analysis) {
                            setMessages((prev) =>
                                prev.map((m) =>
                                    m.id === progressMsgId
                                        ? {
                                            ...m,
                                            content: `**Paper fetched and analyzed!** "${data.paper?.title}"${
                                                data.chunks_failed ? ` (${data.chunks_embedded} of ${(data.chunks_embedded || 0) + (data.chunks_failed || 0)} chunks embedded)` : ''
                                            }\n\nYou can discuss the paper, or ask me to **brainstorm hypotheses**.`,
                                            metadata: {
                                                type: 'paper_analysis' as const,
                                                document_id: data.document_id,
                                                session_id: data.session_id,
                                                paper_analysis: data.paper_analysis,
                                                code_path: data.code_path,
                                            },
                                        }
                                        : m
                                )
                            );
                        } else {
                            setMessages((prev) =>
                                prev.map((m) =>
                                    m.id === progressMsgId
                                        ? { ...m, content: `**Paper fetched!** "${data.paper?.title}" has been processed. You can now ask questions about it.`, metadata: { type: 'text' as const } }
                                        : m
                                )
                            );
                        }
                    }
                } else {
                    // JSON error response (validation, auth)
                    const data = await res.json();
                    throw new Error(data.error || 'Failed to fetch paper');
                }
            } catch (error) {
                const errText = error instanceof Error ? error.message : 'Something went wrong';
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === progressMsgId
                            ? { ...m, content: `**Fetch Error:** ${errText}`, metadata: { type: 'error' as const } }
                            : m
                    )
                );
            } finally {
                setIsProcessing(false);
            }
        },
        [userId, activeConversationId]
    );

    const handleImportPaper = useCallback(
        async (paper: PaperMetadata) => {
            if (!paper.arxiv_id) return;
            setImportingPaper(paper.arxiv_id);
            try {
                await handleFetchArxiv(paper.arxiv_id);
            } finally {
                setImportingPaper(null);
            }
        },
        [handleFetchArxiv]
    );

    // Handle literature search command
    const handleSearchPapers = useCallback(
        async (query: string) => {
            if (!userId) return;

            let convId = activeConversationId;
            if (!convId) {
                const res = await fetch('/api/conversations', { method: 'POST' });
                if (res.ok) {
                    const conv = await res.json();
                    convId = conv.id;
                    skipNextFetchRef.current = true;
                    setActiveConversationId(conv.id);
                } else {
                    return;
                }
            }

            const userMsg: Message = {
                id: crypto.randomUUID(),
                conversation_id: convId!,
                role: 'user',
                content: `Search papers: **${query}**`,
                metadata: { type: 'text' },
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, userMsg]);
            setIsLoading(true);

            try {
                const res = await fetch('/api/literature/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, limit: 10 }),
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Search failed');

                const searchMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: convId!,
                    role: 'assistant',
                    content: data.papers.length > 0
                        ? `Found **${data.papers.length}** papers. Click "Import to VREDA" to fetch and analyze any paper.`
                        : `No papers found for "${query}". Try a different search term.`,
                    metadata: {
                        type: 'literature_search',
                        search_results: data.papers,
                        search_query: query,
                    },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, searchMsg]);
            } catch (error) {
                const errText = error instanceof Error ? error.message : 'Something went wrong';
                const errorMsg: Message = {
                    id: crypto.randomUUID(),
                    conversation_id: convId!,
                    role: 'assistant',
                    content: `**Search Error:** ${errText}`,
                    metadata: { type: 'error' },
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, errorMsg]);
            } finally {
                setIsLoading(false);
            }
        },
        [userId, activeConversationId]
    );

    // Route chat messages through strategist or literature search
    const handleSendMessageWithStrategist = useCallback(
        async (text: string) => {
            const lowerText = text.toLowerCase().trim();

            // Detect "search: <query>" command
            const searchMatch = text.match(/^search:\s*(.+)/i);
            if (searchMatch) {
                await handleSearchPapers(searchMatch[1].trim());
                return;
            }

            const isBrainstormRequest =
                lowerText.includes('brainstorm') ||
                lowerText.includes('hypothes') ||
                lowerText.includes('suggest experiments') ||
                lowerText.includes('what experiments');

            if (
                strategistSessionId &&
                (strategistPhase === 'analysis_complete' || strategistPhase === 'hypothesis_presented') &&
                isBrainstormRequest
            ) {
                await handleRefineHypotheses(text);
            } else {
                await handleSendMessage(text);
            }
        },
        [strategistSessionId, strategistPhase, handleRefineHypotheses, handleSendMessage, handleSearchPapers]
    );

    return (
        <div className="chat-layout">
            <Sidebar
                activeConversationId={activeConversationId}
                onSelect={(id) => {
                    setActiveConversationId(id);
                    setStrategistSessionId(null);
                    setStrategistPhase('idle');
                }}
                onNewConversation={() => {
                    createNewConversation();
                    setStrategistSessionId(null);
                    setStrategistPhase('idle');
                }}
            />

            <main className="chat-main">
                <div className="chat-header">
                    <FlaskConical size={18} color="var(--accent-indigo-light)" />
                    <span className="chat-header-title">
                        {activeConversationId ? 'Research Quest' : 'VREDA.ai Lab'}
                    </span>
                    <span className="chat-header-badge">
                        {strategistLoading
                            ? '⚡ Strategist Working'
                            : isProcessing
                                ? '⚡ Processing'
                                : '● Online'}
                    </span>
                </div>

                <ChatArea
                    messages={messages}
                    isLoading={isLoading}
                    streamingText={streamingText}
                    onSelectHypothesis={handleSelectHypothesis}
                    onRefineHypotheses={handleRefineHypotheses}
                    onApproveBudget={handleApproveBudget}
                    onImportPaper={handleImportPaper}
                    importingPaper={importingPaper}
                    strategistLoading={strategistLoading}
                />

                <ChatInput
                    onSendMessage={handleSendMessageWithStrategist}
                    onUploadFile={handleUploadFile}
                    onFetchArxiv={handleFetchArxiv}
                    disabled={!userId}
                    isProcessing={isProcessing || strategistLoading}
                />
            </main>
        </div>
    );
}
