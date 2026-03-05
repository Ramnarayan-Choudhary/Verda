import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { logger } from '@/lib/logger';

const VALID_DOMAINS = new Set(['ai_ml', 'comp_bio', 'simulation', 'drug_discovery']);
let domainColumnUnavailable = false;
let domainFallbackLogged = false;

function isDomainColumnMissingError(error: { code?: string; message?: string; details?: string | null }): boolean {
    const text = `${error.code || ''} ${error.message || ''} ${error.details || ''}`.toLowerCase();
    return (
        text.includes('domain') &&
        (text.includes('column') || text.includes('schema cache') || text.includes('pgrst204') || text.includes('42703'))
    );
}

export async function POST(request: NextRequest) {
    try {
        const supabase = await createServerSupabaseClient();

        const {
            data: { user },
            error: authError,
        } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        let requestedDomain = 'ai_ml';
        try {
            const rawBody = await request.text();
            if (rawBody.trim()) {
                const parsed = JSON.parse(rawBody) as { domain?: string };
                if (parsed.domain && VALID_DOMAINS.has(parsed.domain)) {
                    requestedDomain = parsed.domain;
                }
            }
        } catch {
            // Keep default domain when body is absent/malformed for backward compatibility.
        }

        const insertWithDomain = async () =>
            supabase
                .from('conversations')
                .insert({ title: 'New Research Quest', user_id: user.id, domain: requestedDomain })
                .select()
                .single();

        const insertWithoutDomain = async () =>
            supabase
                .from('conversations')
                .insert({ title: 'New Research Quest', user_id: user.id })
                .select()
                .single();

        let { data, error } = domainColumnUnavailable ? await insertWithoutDomain() : await insertWithDomain();

        if (error && isDomainColumnMissingError(error)) {
            domainColumnUnavailable = true;
            if (!domainFallbackLogged) {
                domainFallbackLogged = true;
                logger.warn('Conversations insert fallback: domain column not available yet; run apps/web/supabase/004_quest_events_and_domain.sql', { userId: user.id });
            }
            const fallback = await insertWithoutDomain();
            data = fallback.data;
            error = fallback.error;
        }

        if (error) {
            logger.error('Failed to create conversation', new Error(error.message), { userId: user.id });
            return NextResponse.json({ error: 'Failed to create conversation' }, { status: 500 });
        }

        return NextResponse.json(data);
    } catch (error) {
        logger.error('Conversations POST error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

export async function GET() {
    try {
        const supabase = await createServerSupabaseClient();

        const {
            data: { user },
            error: authError,
        } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { data, error } = await supabase
            .from('conversations')
            .select('*')
            .order('created_at', { ascending: false });

        if (error) {
            logger.error('Failed to fetch conversations', new Error(error.message));
            return NextResponse.json({ error: 'Failed to fetch conversations' }, { status: 500 });
        }

        return NextResponse.json(data || []);
    } catch (error) {
        logger.error('Conversations GET error', error instanceof Error ? error : new Error(String(error)));
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
