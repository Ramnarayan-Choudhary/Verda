import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { searchArxiv } from '@/lib/literature/arxiv';
import { searchPapers } from '@/lib/literature/semantic-scholar';
import { logger } from '@/lib/logger';
import type { PaperMetadata, LiteratureSource } from '@/lib/literature/types';

export async function POST(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { query, sources, limit = 10 } = body as {
            query?: string;
            sources?: LiteratureSource[];
            limit?: number;
        };

        if (!query || typeof query !== 'string' || query.trim().length === 0) {
            return NextResponse.json({ error: 'Query is required' }, { status: 400 });
        }

        if (query.length > 500) {
            return NextResponse.json({ error: 'Query too long (max 500 characters)' }, { status: 400 });
        }

        const activeSources: LiteratureSource[] = sources?.length
            ? sources
            : ['arxiv', 'semantic_scholar'];

        const clampedLimit = Math.min(Math.max(limit, 1), 25);

        // Search in parallel across selected sources
        const searchPromises: Promise<PaperMetadata[]>[] = [];

        if (activeSources.includes('arxiv')) {
            searchPromises.push(
                searchArxiv(query, clampedLimit).catch(err => {
                    logger.warn('arXiv search failed (non-fatal)', { error: err instanceof Error ? err.message : String(err) });
                    return [];
                })
            );
        }

        if (activeSources.includes('semantic_scholar')) {
            searchPromises.push(
                searchPapers(query, clampedLimit).catch(err => {
                    logger.warn('Semantic Scholar search failed (non-fatal)', { error: err instanceof Error ? err.message : String(err) });
                    return [];
                })
            );
        }

        const results = await Promise.all(searchPromises);
        const allPapers = results.flat();

        // Deduplicate by arXiv ID (prefer Semantic Scholar for citation counts)
        const seen = new Map<string, PaperMetadata>();
        for (const paper of allPapers) {
            const key = paper.arxiv_id || paper.doi || paper.title.toLowerCase().slice(0, 80);

            const existing = seen.get(key);
            if (!existing) {
                seen.set(key, paper);
            } else if (paper.source === 'semantic_scholar' && existing.source === 'arxiv') {
                // Merge: keep S2 data but add arXiv PDF URL if missing
                seen.set(key, {
                    ...paper,
                    pdf_url: paper.pdf_url || existing.pdf_url,
                    arxiv_id: paper.arxiv_id || existing.arxiv_id,
                });
            }
        }

        const deduplicated = Array.from(seen.values()).slice(0, clampedLimit);

        return NextResponse.json({
            papers: deduplicated,
            total: deduplicated.length,
            query: query.trim(),
        });
    } catch (error) {
        logger.error('Literature search error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
