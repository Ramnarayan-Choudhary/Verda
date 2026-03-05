import { NextRequest, NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { validateUUID } from '@/lib/validation';
import { ValidationError } from '@/lib/errors';
import { logger } from '@/lib/logger';
import { isQuestEventsUnavailableError } from '@/lib/quest-events';

export async function GET(request: NextRequest) {
  try {
    const supabase = await createServerSupabaseClient();
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const conversationId = request.nextUrl.searchParams.get('conversation_id');
    const before = request.nextUrl.searchParams.get('before');
    const limitParam = request.nextUrl.searchParams.get('limit');

    if (!conversationId) {
      return NextResponse.json({ error: 'conversation_id is required' }, { status: 400 });
    }

    try {
      validateUUID(conversationId, 'conversation_id');
    } catch (error) {
      if (error instanceof ValidationError) {
        return NextResponse.json({ error: error.message }, { status: 400 });
      }
      throw error;
    }

    let limit = 120;
    if (limitParam) {
      const parsed = Number.parseInt(limitParam, 10);
      if (!Number.isNaN(parsed)) {
        limit = Math.max(1, Math.min(300, parsed));
      }
    }

    let query = supabase
      .from('quest_events')
      .select('*')
      .eq('conversation_id', conversationId)
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (before) {
      query = query.lt('created_at', before);
    }

    const { data, error } = await query;

    if (error) {
      if (isQuestEventsUnavailableError(error)) {
        return NextResponse.json([], {
          headers: { 'x-quest-events-unavailable': '1' },
        });
      }

      logger.error('Failed to fetch quest events', new Error(error.message), {
        conversationId,
        userId: user.id,
      });
      return NextResponse.json({ error: 'Failed to fetch quest events' }, { status: 500 });
    }

    return NextResponse.json((data || []).reverse());
  } catch (error) {
    logger.error('Quest events GET error', error instanceof Error ? error : new Error(String(error)));
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
