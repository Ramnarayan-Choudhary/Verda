/**
 * Load an arXiv paper into IRIS by fetching its metadata via the arXiv API
 * (no PDF download — uses the existing @/lib/literature/arxiv client which
 * calls export.arxiv.org/api/query, not the PDF endpoint that arXiv blocks).
 */
import { NextRequest, NextResponse } from 'next/server';
import { fetchByArxivId } from '@/lib/literature/arxiv';
import { irisProxy } from '@/lib/iris-proxy';

const ARXIV_RE = /arxiv\.org\/(?:abs|pdf)\/([\d.v]+)/i;

export async function POST(req: NextRequest) {
    const body = await req.json();
    const url: unknown = body?.url;

    if (typeof url !== 'string' || !url.trim()) {
        return NextResponse.json({ error: 'url is required' }, { status: 400 });
    }

    const match = url.match(ARXIV_RE);
    if (!match) {
        return NextResponse.json({ error: 'Not a valid arXiv URL (expected arxiv.org/abs/ID or arxiv.org/pdf/ID)' }, { status: 400 });
    }

    const arxivId = match[1].replace(/v\d+$/, '');

    const paper = await fetchByArxivId(arxivId);
    if (!paper) {
        return NextResponse.json({ error: `Could not fetch metadata for arXiv:${arxivId}` }, { status: 404 });
    }

    // Build a rich text representation the IRIS backend can use as paper context
    const fullText = [
        `Title: ${paper.title}`,
        `Authors: ${paper.authors.join(', ')}`,
        `Published: ${paper.published}`,
        `Categories: ${paper.categories.join(', ')}`,
        '',
        `Abstract:`,
        paper.abstract,
    ].join('\n');

    // Add to IRIS knowledge store — the backend reads knowledge_chunks[i].full_text
    // and knowledge_chunks[i].abstract when generating paper-grounded hypotheses
    const knowledgeRes = await irisProxy('/api/add_knowledge', {
        method: 'POST',
        body: {
            text: fullText,
            abstract: paper.abstract,
            source: paper.pdf_url || `https://arxiv.org/abs/${arxivId}`,
        },
    });

    const knowledgeData = await knowledgeRes.json();
    if (!knowledgeRes.ok) {
        return NextResponse.json(
            { error: knowledgeData.error || `IRIS rejected knowledge (HTTP ${knowledgeRes.status})` },
            { status: 502 }
        );
    }

    return NextResponse.json({
        title: paper.title,
        abstract: paper.abstract,
        arxiv_id: arxivId,
        chunk_id: knowledgeData.id,
    });
}
