import { NextRequest, NextResponse } from 'next/server';
import { extractTextFromPDF } from '@/lib/pdf/extract';
import { semanticChunkTextWithIndices } from '@/lib/pdf/chunker';
import { batchEmbedTexts } from '@/lib/embeddings';
import { runInitialAnalysis } from '@/lib/agents/strategist-room';
import { isArxivId, normalizeArxivId } from '@/lib/literature/arxiv';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { createAdminSupabaseClient } from '@/lib/supabase/admin';
import { validateUUID, validateFileUpload, validatePDFMagicBytes } from '@/lib/validation';
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

    const {
        data: { user },
        error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const formData = await request.formData();
    const file = formData.get('file') as File;
    const conversationId = formData.get('conversation_id') as string;

    // Validate inputs (pre-stream — JSON errors)
    try {
        validateFileUpload(file);
        validateUUID(conversationId, 'conversation_id');
    } catch (error) {
        if (error instanceof ValidationError) {
            return NextResponse.json({ error: error.message }, { status: 400 });
        }
        throw error;
    }

    // Read buffer and validate PDF magic bytes (pre-stream)
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    try {
        await validatePDFMagicBytes(buffer);
    } catch (error) {
        if (error instanceof ValidationError) {
            return NextResponse.json({ error: error.message }, { status: 400 });
        }
        throw error;
    }

    // --- Begin NDJSON stream ---
    const encoder = new TextEncoder();
    let docId: string | undefined;

    const stream = new ReadableStream({
        async start(controller) {
            const send = (event: Record<string, unknown>) =>
                sendEvent(controller, encoder, event);

            // Try to detect arXiv ID from filename (e.g., "2503.08979.pdf" or "2503.08979v2.pdf")
            const filenameBase = file.name.replace(/\.pdf$/i, '');
            const detectedArxivId = isArxivId(filenameBase) ? normalizeArxivId(filenameBase) : null;
            if (detectedArxivId) {
                logger.info('Detected arXiv ID from filename', { filename: file.name, arxivId: detectedArxivId });
            }

            try {
                // Step 1: Upload PDF to Supabase Storage
                send({ type: 'progress', step: 'upload_storage', message: 'Uploading PDF to cloud storage...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'upload_storage_started',
                    level: 'info',
                    status: 'active',
                    message: `Uploading PDF ${file.name} to storage.`,
                });
                const storagePath = `${user.id}/${Date.now()}_${file.name}`;

                const { error: uploadError } = await adminSupabase.storage
                    .from(config.supabase.paperBucket)
                    .upload(storagePath, buffer, {
                        contentType: 'application/pdf',
                        upsert: true,
                    });

                if (uploadError) {
                    logger.error('Storage upload failed', new Error(uploadError.message), {
                        storagePath,
                        userId: user.id,
                    });
                    send({ type: 'error', message: `Failed to upload file to storage: ${uploadError.message}` });
                    controller.close();
                    return;
                }

                logger.info('PDF uploaded to storage', { storagePath });
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'upload_storage_completed',
                    level: 'success',
                    status: 'done',
                    message: `PDF ${file.name} uploaded to storage.`,
                });

                // Step 2: Create document record
                const { data: doc, error: docError } = await supabase
                    .from('documents')
                    .insert({
                        user_id: user.id,
                        conversation_id: conversationId,
                        filename: file.name,
                        storage_path: storagePath,
                        status: 'processing',
                    })
                    .select()
                    .single();

                if (docError || !doc) {
                    logger.error('Document record creation failed', docError ? new Error(docError.message) : new Error('No data returned'));
                    send({ type: 'error', message: 'Failed to create document record' });
                    controller.close();
                    return;
                }

                docId = doc.id;
                saveCheckpoint(supabase, doc.id, 'upload');

                // Step 3: Extract text from PDF
                send({ type: 'progress', step: 'extract_text', message: 'Extracting text from PDF...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'extract_text_started',
                    level: 'info',
                    status: 'active',
                    message: 'Text extraction started.',
                });
                saveCheckpoint(supabase, doc.id, 'extract_text');
                const text = await extractTextFromPDF(buffer);

                if (!text.trim()) {
                    saveFailure(supabase, doc.id, 'extract_text', 'No text extracted from PDF');
                    send({ type: 'error', message: 'Could not extract text from PDF. The file may be image-based.' });
                    controller.close();
                    return;
                }

                // Step 4: Chunk the text
                saveCheckpoint(supabase, doc.id, 'chunk');
                const chunks = semanticChunkTextWithIndices(text);
                send({ type: 'progress', step: 'chunking', message: `Split into ${chunks.length} text segments` });
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'chunking_completed',
                    level: 'success',
                    status: 'done',
                    message: `Chunking complete with ${chunks.length} segments.`,
                });

                // Step 5: Embed chunks with progress callback (throttled)
                saveCheckpoint(supabase, doc.id, 'embed');
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'embedding_started',
                    level: 'info',
                    status: 'active',
                    message: 'Embedding pipeline started.',
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
                        conversation_id: conversationId,
                        document_id: doc.id,
                        user_id: user.id,
                        room: 'library',
                        event_key: 'embedding_partial_warning',
                        level: 'warn',
                        status: 'warning',
                        message: `${embedResult.failed} chunks failed during embedding.`,
                        metadata: { failed: embedResult.failed, succeeded: embedResult.succeeded },
                    });
                }

                // Step 6: Store only successful chunks
                saveCheckpoint(supabase, doc.id, 'store_chunks');
                send({ type: 'progress', step: 'storing_chunks', message: 'Saving embedded chunks to database...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'store_chunks_started',
                    level: 'info',
                    status: 'active',
                    message: 'Saving embedded chunks to database.',
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
                    conversation_id: conversationId,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'store_chunks_completed',
                    level: 'success',
                    status: 'done',
                    message: `Stored ${chunkRecords.length} embedded chunks.`,
                });

                // Step 7: Run Strategist Room (Parser + Research Intelligence + Scout)
                saveCheckpoint(supabase, doc.id, 'parse_analysis');
                send({ type: 'progress', step: 'strategist', message: 'Running AI analysis (Parser + Scout)...' });
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    document_id: doc.id,
                    user_id: user.id,
                    room: 'hypothesis',
                    event_key: 'strategist_analysis_started',
                    level: 'info',
                    status: 'active',
                    message: 'Strategist analysis started.',
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
                            conversation_id: conversationId,
                            document_id: doc.id,
                            user_id: user.id,
                            room: 'hypothesis',
                            event_key: 'research_intelligence_started',
                            level: 'info',
                            status: 'active',
                            message: 'Research intelligence enrichment started.',
                        });
                        analysisState = await runInitialAnalysis(paperContext, doc.id, conversationId, user.id, detectedArxivId);
                        sessionId = analysisState.session_id;

                        const { error: sessionError } = await supabase
                            .from('strategist_sessions')
                            .insert({
                                id: analysisState.session_id,
                                document_id: doc.id,
                                conversation_id: conversationId,
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
                            conversation_id: conversationId,
                            document_id: doc.id,
                            session_id: sessionId,
                            user_id: user.id,
                            room: 'hypothesis',
                            event_key: 'strategist_analysis_completed',
                            level: analysisState.paper_analysis ? 'success' : 'warn',
                            status: analysisState.paper_analysis ? 'done' : 'warning',
                            message: analysisState.paper_analysis
                                ? 'Strategist analysis completed with paper insights.'
                                : 'Strategist session created without paper analysis output.',
                        });
                    }
                } catch (err) {
                    logger.warn('Strategist Room analysis failed (non-fatal)', {
                        documentId: doc.id,
                        error: err instanceof Error ? err.message : String(err),
                    });
                    void appendQuestEvent(supabase, {
                        conversation_id: conversationId,
                        document_id: doc.id,
                        user_id: user.id,
                        room: 'hypothesis',
                        event_key: 'strategist_analysis_failed',
                        level: 'warn',
                        status: 'warning',
                        message: `Strategist analysis warning: ${err instanceof Error ? err.message : String(err)}`,
                    });
                }

                // Step 8: Mark document as ready (after all processing including analysis)
                markComplete(supabase, doc.id);

                // Step 9: Store analysis message (DB save uses admin client for reliability)
                if (analysisState?.paper_analysis) {
                    await supabase.from('messages').insert({
                        conversation_id: conversationId,
                        role: 'assistant',
                        content: `## Paper Analysis Complete\n\nI've analyzed **"${analysisState.paper_analysis.title || file.name}"** and assessed code availability.`,
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

                // Step 10: Complete
                send({
                    type: 'complete',
                    data: {
                        success: true,
                        document_id: doc.id,
                        chunks_count: chunks.length,
                        chunks_embedded: embedResult.succeeded,
                        chunks_failed: embedResult.failed,
                        session_id: sessionId,
                        phase: analysisState?.phase || (sessionId ? 'analysis_complete' : 'idle'),
                        paper_analysis: analysisState?.paper_analysis || null,
                        code_path: analysisState?.code_path || null,
                        research_intelligence: analysisState?.research_intelligence || null,
                    },
                });
                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    document_id: doc.id,
                    session_id: sessionId,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'upload_pipeline_complete',
                    level: 'success',
                    status: 'done',
                    message: `Upload pipeline complete for ${file.name}.`,
                });
            } catch (error) {
                logger.error('Upload pipeline error', error instanceof Error ? error : new Error(String(error)));
                send({
                    type: 'error',
                    message: error instanceof Error ? error.message : 'Internal server error during PDF processing',
                });

                void appendQuestEvent(supabase, {
                    conversation_id: conversationId,
                    document_id: docId ?? null,
                    user_id: user.id,
                    room: 'library',
                    event_key: 'upload_pipeline_error',
                    level: 'error',
                    status: 'error',
                    message: error instanceof Error ? error.message : 'Upload pipeline failed',
                });

                if (docId) {
                    saveFailure(supabase, docId, 'upload', error instanceof Error ? error.message : 'Unknown error');
                }
            } finally {
                controller.close();
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
