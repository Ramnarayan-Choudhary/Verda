import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { createAdminSupabaseClient } from '@/lib/supabase/admin';
import { fetchByArxivId, isArxivId, normalizeArxivId } from '@/lib/literature/arxiv';
import { getPaper } from '@/lib/literature/semantic-scholar';
import { extractTextFromPDF } from '@/lib/pdf/extract';
import { chunkTextWithIndices } from '@/lib/pdf/chunker';
import { batchEmbedTexts } from '@/lib/embeddings/gemini';
import { retrieveRelevantChunks } from '@/lib/agents/strategist';
import { runInitialAnalysis } from '@/lib/agents/strategist-room';
import { validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';

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

            try {
                // Step 1: Fetch paper metadata from arXiv
                send({ type: 'progress', step: 'metadata', message: 'Fetching paper metadata from arXiv...' });
                logger.info('Fetching arXiv paper', { arxiv_id: normalizedId });
                const arxivPaper = await fetchByArxivId(normalizedId);

                if (!arxivPaper) {
                    send({ type: 'error', message: `Paper not found on arXiv: ${normalizedId}` });
                    controller.close();
                    return;
                }

                // Step 2: Enrich with Semantic Scholar data
                let citationCount: number | undefined;
                try {
                    send({ type: 'progress', step: 'metadata', message: 'Enriching with citation data...' });
                    const s2Paper = await getPaper(`ArXiv:${normalizedId}`);
                    if (s2Paper) citationCount = s2Paper.citation_count;
                } catch {
                    logger.warn('S2 enrichment failed (non-fatal)', { arxiv_id: normalizedId });
                }

                // Step 3: Download PDF
                const pdfUrl = arxivPaper.pdf_url;
                if (!pdfUrl) {
                    send({ type: 'error', message: 'No PDF URL available for this paper' });
                    controller.close();
                    return;
                }

                send({ type: 'progress', step: 'download', message: 'Downloading PDF from arXiv...' });
                logger.info('Downloading arXiv PDF', { url: pdfUrl });
                const pdfResponse = await fetch(pdfUrl, { redirect: 'follow' });

                if (!pdfResponse.ok) {
                    send({ type: 'error', message: 'Failed to download PDF from arXiv' });
                    controller.close();
                    return;
                }

                const pdfBuffer = Buffer.from(await pdfResponse.arrayBuffer());
                const sizeMB = (pdfBuffer.length / 1024 / 1024).toFixed(1);
                send({ type: 'progress', step: 'download', message: `PDF downloaded (${sizeMB} MB)` });

                // Validate PDF magic bytes
                if (pdfBuffer.length < 4 || pdfBuffer.subarray(0, 4).toString('ascii') !== '%PDF') {
                    logger.error('Downloaded content is not a valid PDF', new Error('Invalid PDF response'), {
                        url: pdfUrl,
                        contentType: pdfResponse.headers.get('content-type'),
                    });
                    send({ type: 'error', message: 'arXiv returned invalid content instead of PDF. Please try again.' });
                    controller.close();
                    return;
                }

                // Step 4: Upload to Supabase Storage
                send({ type: 'progress', step: 'upload_storage', message: 'Storing PDF in cloud...' });
                const filename = `${normalizedId.replace('.', '_')}.pdf`;
                const storagePath = `${user.id}/${Date.now()}_${filename}`;

                const { error: uploadError } = await adminSupabase.storage
                    .from('Research-Paper')
                    .upload(storagePath, pdfBuffer, {
                        contentType: 'application/pdf',
                        upsert: true,
                    });

                if (uploadError) {
                    logger.error('Storage upload failed', new Error(uploadError.message));
                    send({ type: 'error', message: 'Failed to store PDF' });
                    controller.close();
                    return;
                }

                // Step 5: Create document record
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
                    controller.close();
                    return;
                }

                docId = doc.id;

                // Step 6: Extract text
                send({ type: 'progress', step: 'extract_text', message: 'Extracting text from PDF...' });
                const text = await extractTextFromPDF(pdfBuffer);

                if (!text.trim()) {
                    await supabase.from('documents').update({ status: 'error' }).eq('id', doc.id);
                    send({ type: 'error', message: 'Could not extract text from PDF. The file may be image-based.' });
                    controller.close();
                    return;
                }

                // Step 7: Chunk text
                const chunks = chunkTextWithIndices(text);
                send({ type: 'progress', step: 'chunking', message: `Split into ${chunks.length} text segments` });

                // Step 8: Embed with progress callback (throttled to every 3rd chunk)
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
                }

                // Step 9: Store only successful chunks
                send({ type: 'progress', step: 'storing_chunks', message: 'Saving embedded chunks to database...' });
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

                // Step 10: Update document status
                await supabase.from('documents').update({ status: 'ready' }).eq('id', doc.id);

                // Step 11: Run Strategist Room (Parser + Research Intelligence + Scout)
                send({ type: 'progress', step: 'strategist', message: 'Running AI analysis (Parser + Scout)...' });
                let sessionId: string | null = null;
                let analysisState = null;
                try {
                    const ragChunks = await retrieveRelevantChunks(
                        doc.id,
                        'hypothesis variables methodology results conclusions experiment design architecture model training',
                        supabase,
                        15
                    );
                    const paperContext = ragChunks.map(c => c.content).join('\n\n---\n\n');

                    if (paperContext.trim()) {
                        send({ type: 'progress', step: 'research_intelligence', message: 'Gathering code repos, citations, and related work...' });
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
                    }
                } catch (err) {
                    logger.warn('Strategist Room analysis failed (non-fatal)', {
                        documentId: doc.id,
                        error: err instanceof Error ? err.message : String(err),
                    });
                }

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
            } catch (error) {
                logger.error('Literature fetch pipeline error', error instanceof Error ? error : new Error(String(error)));
                send({
                    type: 'error',
                    message: error instanceof Error ? error.message : 'Internal server error',
                });

                if (docId) {
                    try {
                        await supabase.from('documents').update({ status: 'error' }).eq('id', docId);
                    } catch (updateErr) {
                        logger.error('Failed to update document status', updateErr instanceof Error ? updateErr : new Error(String(updateErr)));
                    }
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
