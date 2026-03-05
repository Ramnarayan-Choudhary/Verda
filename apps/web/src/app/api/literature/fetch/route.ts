import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { createAdminSupabaseClient } from '@/lib/supabase/admin';
import { fetchByArxivId, isArxivId, normalizeArxivId } from '@/lib/literature/arxiv';
import { getPaper } from '@/lib/literature/semantic-scholar';
import { extractTextFromPDF } from '@/lib/pdf/extract';
import { semanticChunkTextWithIndices } from '@/lib/pdf/chunker';
import { batchEmbedTexts } from '@/lib/embeddings';
import { runInitialAnalysis } from '@/lib/agents/strategist-room';
import { validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';
import { config } from '@/lib/config';
import { saveCheckpoint, saveFailure, markComplete } from '@/lib/pipeline/checkpoint';
import { appendQuestEvent } from '@/lib/quest-events';

export const maxDuration = 120;
export const runtime = 'nodejs';

/** Send one NDJSON line to the stream (safe if controller is already closed). */
function sendEvent(
    controller: ReadableStreamDefaultController,
    encoder: TextEncoder,
    event: Record<string, unknown>
) {
    try {
        controller.enqueue(encoder.encode(JSON.stringify(event) + '\n'));
    } catch {
        // Controller already closed (client disconnected or stream ended)
    }
}

export async function POST(request: NextRequest) {
    // --- Pre-stream validation (returns JSON on failure) ---
    const supabase = await createServerSupabaseClient();
    const adminSupabase = createAdminSupabaseClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    if (authError || !user) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const { arxiv_id, conversation_id } = body as {
        arxiv_id?: string;
        conversation_id?: string;
    };

    if (!arxiv_id || !isArxivId(arxiv_id)) {
        return NextResponse.json(
            { error: 'Valid arXiv ID is required (e.g., 2301.07041)' },
            { status: 400 }
        );
    }

    try {
        validateUUID(conversation_id || '', 'conversation_id');
    } catch (error) {
        if (error instanceof ValidationError) {
            return NextResponse.json({ error: error.message }, { status: 400 });
        }
        throw error;
    }

    const normalizedId = normalizeArxivId(arxiv_id);

    // --- Begin NDJSON stream ---
    const encoder = new TextEncoder();
    let docId: string | undefined;

    const stream = new ReadableStream({
        async start(controller) {
            const send = (event: Record<string, unknown>) =>
                sendEvent(controller, encoder, event);
            let closed = false;
            const safeClose = () => {
                if (!closed) { closed = true; controller.close(); }
            };

            try {
                // Step 1: Fetch paper metadata (arXiv with S2 fallback)
                send({ type: 'progress', step: 'metadata', message: 'Fetching paper metadata...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_metadata_started',
                    level: 'info',
                    status: 'active',
                    message: `Fetching metadata for arXiv:${normalizedId}.`,
                });
                logger.info('Fetching arXiv paper', { arxiv_id: normalizedId });
                const arxivPaper = await fetchByArxivId(normalizedId);

                if (!arxivPaper) {
                    send({ type: 'error', message: `Paper not found: ${normalizedId}. Neither arXiv nor Semantic Scholar returned results.` });
                    safeClose();
                    return;
                }

                // Step 2: Enrich with Semantic Scholar data (single call, cached for PDF URL)
                let citationCount: number | undefined;
                let s2PdfUrl: string | undefined;
                try {
                    send({ type: 'progress', step: 'metadata', message: 'Enriching with citation data...' });
                    const s2Paper = await getPaper(`ArXiv:${normalizedId}`);
                    if (s2Paper) {
                        citationCount = s2Paper.citation_count;
                        s2PdfUrl = s2Paper.pdf_url;
                    }
                } catch {
                    logger.warn('S2 enrichment failed (non-fatal)', { arxiv_id: normalizedId });
                }

                // Step 3: Download PDF (try multiple sources, validate each is actually a PDF)
                const pdfUrl = arxivPaper.pdf_url;
                if (!pdfUrl && !s2PdfUrl) {
                    send({ type: 'error', message: 'No PDF URL available for this paper' });
                    safeClose();
                    return;
                }

                send({ type: 'progress', step: 'download', message: 'Downloading PDF...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_download_started',
                    level: 'info',
                    status: 'active',
                    message: `Downloading PDF for arXiv:${normalizedId}.`,
                });

                // Build deduplicated list of PDF URLs to try
                const pdfUrlCandidates: string[] = [];
                // Prefer S2 open-access URL first (most reliable when arXiv is blocked)
                if (s2PdfUrl) pdfUrlCandidates.push(s2PdfUrl);
                if (pdfUrl) pdfUrlCandidates.push(pdfUrl);
                pdfUrlCandidates.push(`https://arxiv.org/pdf/${normalizedId}`);
                pdfUrlCandidates.push(`https://export.arxiv.org/pdf/${normalizedId}`);
                const uniquePdfUrls = [...new Set(pdfUrlCandidates)];

                let pdfBuffer: Buffer | null = null;
                for (const candidateUrl of uniquePdfUrls) {
                    logger.info('Trying PDF download', { url: candidateUrl });
                    try {
                        const resp = await fetch(candidateUrl, { redirect: 'follow' });
                        if (!resp.ok) {
                            logger.warn('PDF download returned non-OK status', {
                                url: candidateUrl,
                                status: resp.status,
                            });
                            continue;
                        }

                        // Reject HTML responses (arXiv CAPTCHA pages return 200 with text/html)
                        const contentType = resp.headers.get('content-type') || '';
                        if (contentType.includes('text/html')) {
                            logger.warn('PDF URL returned HTML instead of PDF (likely CAPTCHA)', {
                                url: candidateUrl,
                                contentType,
                            });
                            continue;
                        }

                        // Read and validate magic bytes
                        const buf = Buffer.from(await resp.arrayBuffer());
                        if (buf.length >= 4 && buf.subarray(0, 4).toString('ascii') === '%PDF') {
                            pdfBuffer = buf;
                            logger.info('Valid PDF downloaded', { url: candidateUrl, bytes: buf.length });
                            break;
                        }

                        logger.warn('Downloaded content is not a valid PDF', {
                            url: candidateUrl,
                            contentType,
                            firstBytes: buf.subarray(0, 20).toString('ascii'),
                        });
                    } catch (err) {
                        logger.warn('PDF download error, trying next URL', {
                            url: candidateUrl,
                            error: err instanceof Error ? err.message : String(err),
                        });
                    }
                }

                if (!pdfBuffer) {
                    send({ type: 'error', message: 'Failed to download PDF from all sources. arXiv may be rate-limiting your IP. Please try again in a few minutes, or upload the PDF manually.' });
                    safeClose();
                    return;
                }

                const sizeMB = (pdfBuffer.length / 1024 / 1024).toFixed(1);
                send({ type: 'progress', step: 'download', message: `PDF downloaded (${sizeMB} MB)` });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_download_completed',
                    level: 'success',
                    status: 'done',
                    message: `Downloaded PDF (${sizeMB} MB).`,
                });

                // Step 4: Upload to Supabase Storage
                send({ type: 'progress', step: 'upload_storage', message: 'Storing PDF in cloud...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_store_started',
                    level: 'info',
                    status: 'active',
                    message: 'Storing fetched PDF to cloud storage.',
                });
                const filename = `${normalizedId.replace('.', '_')}.pdf`;
                const storagePath = `${user.id}/${Date.now()}_${filename}`;

                const { error: uploadError } = await adminSupabase.storage
                    .from(config.supabase.paperBucket)
                    .upload(storagePath, pdfBuffer, {
                        contentType: 'application/pdf',
                        upsert: true,
                    });

                if (uploadError) {
                    logger.error('Storage upload failed', new Error(uploadError.message));
                    send({ type: 'error', message: 'Failed to store PDF' });
                    safeClose();
                    return;
                }

                // Step 5: Create document record (include arXiv ID in metadata for hypothesis service)
                const { data: doc, error: docError } = await supabase
                    .from('documents')
                    .insert({
                        user_id: user.id,
                        conversation_id: conversation_id!,
                        filename,
                        storage_path: storagePath,
                        status: 'processing',
                    })
                    .select()
                    .single();

                if (docError || !doc) {
                    logger.error('Document record creation failed', docError ? new Error(docError.message) : new Error('No data'));
                    send({ type: 'error', message: 'Failed to create document record' });
                    safeClose();
                    return;
                }

                docId = doc.id;
                saveCheckpoint(supabase, doc.id, 'upload');

                // Step 6: Extract text
                saveCheckpoint(supabase, doc.id, 'extract_text');
                send({ type: 'progress', step: 'extract_text', message: 'Extracting text from PDF...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_extract_started',
                    level: 'info',
                    status: 'active',
                    message: 'Text extraction started for fetched PDF.',
                });
                const text = await extractTextFromPDF(pdfBuffer);

                if (!text.trim()) {
                    saveFailure(supabase, doc.id, 'extract_text', 'No text extracted from PDF');
                    send({ type: 'error', message: 'Could not extract text from PDF. The file may be image-based.' });
                    safeClose();
                    return;
                }

                // Step 7: Chunk text
                saveCheckpoint(supabase, doc.id, 'chunk');
                const chunks = semanticChunkTextWithIndices(text);
                send({ type: 'progress', step: 'chunking', message: `Split into ${chunks.length} text segments` });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_chunking_completed',
                    level: 'success',
                    status: 'done',
                    message: `Chunking complete with ${chunks.length} segments.`,
                });

                // Step 8: Embed with progress callback (throttled to every 3rd chunk)
                saveCheckpoint(supabase, doc.id, 'embed');
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_embedding_started',
                    level: 'info',
                    status: 'active',
                    message: 'Embedding started for fetched paper.',
                });
                const embedResult = await batchEmbedTexts(
                    chunks.map(c => c.content),
                    (current, total) => {
                        if (current % 3 === 0 || current === total || current === 1) {
                            send({
                                type: 'progress',
                                step: 'embedding',
                                message: `Embedding chunks (${current}/${total})...`,
                                current,
                                total,
                            });
                        }
                    }
                );

                if (embedResult.failed > 0) {
                    send({
                        type: 'warning',
                        step: 'embedding',
                        message: `${embedResult.failed} of ${chunks.length} chunks failed to embed (rate limit). ${embedResult.succeeded} chunks saved successfully.`,
                    });
                    void appendQuestEvent(supabase, {
                        conversation_id: conversation_id!,
                        document_id: doc.id,
                        user_id: user.id,
                        room: 'library',
                        event_key: 'arxiv_embedding_partial_warning',
                        level: 'warn',
                        status: 'warning',
                        message: `${embedResult.failed} chunks failed during embedding.`,
                        metadata: { failed: embedResult.failed, succeeded: embedResult.succeeded },
                    });
                }

                // Step 9: Store only successful chunks
                saveCheckpoint(supabase, doc.id, 'store_chunks');
                send({ type: 'progress', step: 'storing_chunks', message: 'Saving embedded chunks to database...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_store_chunks_started',
                    level: 'info',
                    status: 'active',
                    message: 'Saving fetched paper chunks to database.',
                });
                const chunkRecords = chunks
                    .map((chunk, i) =>
                        embedResult.embeddings[i] !== null
                            ? {
                                document_id: doc.id,
                                content: chunk.content,
                                embedding: JSON.stringify(embedResult.embeddings[i]),
                                chunk_index: chunk.index,
                            }
                            : null
                    )
                    .filter((r): r is NonNullable<typeof r> => r !== null);

                for (let i = 0; i < chunkRecords.length; i += 50) {
                    const batch = chunkRecords.slice(i, i + 50);
                    const { error: chunkError } = await supabase.from('document_chunks').insert(batch);
                    if (chunkError) {
                        logger.error('Chunk insert failed', new Error(chunkError.message), {
                            documentId: doc.id,
                            batchStart: i,
                        });
                    }
                }
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_store_chunks_completed',
                    level: 'success',
                    status: 'done',
                    message: `Stored ${chunkRecords.length} fetched chunks.`,
                });

                // Step 10: Run Strategist Room (Parser + Research Intelligence + Scout)
                saveCheckpoint(supabase, doc.id, 'parse_analysis');
                send({ type: 'progress', step: 'strategist', message: 'Running AI analysis (Parser + Scout)...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'hypothesis',
                    event_key: 'arxiv_strategist_started',
                    level: 'info',
                    status: 'active',
                    message: 'Strategist analysis started for fetched paper.',
                });
                let sessionId: string | null = null;
                let analysisState = null;
                try {
                    // Use raw extracted text (first 30K chars) for initial analysis.
                    // RAG-retrieved chunks can miss the abstract/intro for survey papers,
                    // causing the parser to fail on required fields (title, abstract_summary).
                    const paperContext = text.substring(0, 30000);

                    if (paperContext.trim()) {
                        send({ type: 'progress', step: 'research_intelligence', message: 'Gathering code repos, citations, and related work...' });
                        void appendQuestEvent(supabase, {
                            conversation_id: conversation_id!,
                            document_id: doc.id,
                            user_id: user.id,
                            room: 'hypothesis',
                            event_key: 'arxiv_research_intelligence_started',
                            level: 'info',
                            status: 'active',
                            message: 'Research intelligence enrichment started for fetched paper.',
                        });
                        analysisState = await runInitialAnalysis(paperContext, doc.id, conversation_id!, user.id, normalizedId);
                        sessionId = analysisState.session_id;

                        const { error: sessionError } = await supabase
                            .from('strategist_sessions')
                            .insert({
                                id: analysisState.session_id,
                                document_id: doc.id,
                                conversation_id: conversation_id!,
                                user_id: user.id,
                                state: analysisState,
                                phase: analysisState.phase,
                            });

                        if (sessionError) {
                            logger.warn('Failed to store strategist session', {
                                sessionId: analysisState.session_id,
                                error: sessionError.message,
                            });
                        }

                        void appendQuestEvent(supabase, {
                            conversation_id: conversation_id!,
                            document_id: doc.id,
                            session_id: sessionId,
                            user_id: user.id,
                            room: 'hypothesis',
                            event_key: 'arxiv_strategist_completed',
                            level: analysisState.paper_analysis ? 'success' : 'warn',
                            status: analysisState.paper_analysis ? 'done' : 'warning',
                            message: analysisState.paper_analysis
                                ? 'Strategist analysis complete for fetched paper.'
                                : 'Strategist session created without paper analysis output.',
                        });
                    }
                } catch (err) {
                    logger.warn('Strategist Room analysis failed (non-fatal)', {
                        documentId: doc.id,
                        error: err instanceof Error ? err.message : String(err),
                    });
                    void appendQuestEvent(supabase, {
                        conversation_id: conversation_id!,
                        document_id: doc.id,
                        user_id: user.id,
                        room: 'hypothesis',
                        event_key: 'arxiv_strategist_warning',
                        level: 'warn',
                        status: 'warning',
                        message: `Strategist analysis warning: ${err instanceof Error ? err.message : String(err)}`,
                    });
                }

                // Step 11: Mark document as ready (after all processing including analysis)
                markComplete(supabase, doc.id);

                // Step 12: Store analysis message
                if (analysisState?.paper_analysis) {
                    await supabase.from('messages').insert({
                        conversation_id: conversation_id!,
                        role: 'assistant',
                        content: `## Paper Fetched & Analyzed\n\nI fetched **"${arxivPaper.title}"** from arXiv (${normalizedId}) and ran the analysis.${citationCount ? ` This paper has **${citationCount.toLocaleString()} citations**.` : ''}`,
                        metadata: {
                            type: 'paper_analysis',
                            document_id: doc.id,
                            session_id: sessionId,
                            paper_analysis: analysisState.paper_analysis,
                            code_path: analysisState.code_path,
                            research_intelligence: analysisState.research_intelligence ?? undefined,
                        },
                    });
                }

                // Step 13: Complete
                send({
                    type: 'complete',
                    data: {
                        success: true,
                        document_id: doc.id,
                        session_id: sessionId,
                        phase: analysisState?.phase || (sessionId ? 'analysis_complete' : 'idle'),
                        paper: {
                            ...arxivPaper,
                            citation_count: citationCount,
                        },
                        paper_analysis: analysisState?.paper_analysis || null,
                        code_path: analysisState?.code_path || null,
                        research_intelligence: analysisState?.research_intelligence || null,
                        chunks_embedded: embedResult.succeeded,
                        chunks_failed: embedResult.failed,
                    },
                });
                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: doc.id,
                    session_id: sessionId,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_pipeline_complete',
                    level: 'success',
                    status: 'done',
                    message: `Fetch pipeline complete for arXiv:${normalizedId}.`,
                });
            } catch (error) {
                logger.error('Literature fetch pipeline error', error instanceof Error ? error : new Error(String(error)));
                send({
                    type: 'error',
                    message: error instanceof Error ? error.message : 'Internal server error',
                });

                void appendQuestEvent(supabase, {
                    conversation_id: conversation_id!,
                    document_id: docId ?? null,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'arxiv_pipeline_error',
                    level: 'error',
                    status: 'error',
                    message: error instanceof Error ? error.message : 'arXiv fetch pipeline failed',
                });

                if (docId) {
                    saveFailure(supabase, docId, 'upload', error instanceof Error ? error.message : 'Unknown error');
                }
            } finally {
                safeClose();
            }
        },
    });

    return new Response(stream, {
        headers: {
            'Content-Type': 'application/x-ndjson',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    });
}
