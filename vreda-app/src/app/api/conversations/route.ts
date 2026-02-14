import { NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { logger } from '@/lib/logger';

export async function POST() {
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
            .insert({ title: 'New Research Quest', user_id: user.id })
            .select()
            .single();

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
