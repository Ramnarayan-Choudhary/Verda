import type { SupabaseClient } from '@supabase/supabase-js';
import { logger } from '@/lib/logger';
import type { QuestEventLevel, QuestEventStatus, QuestRoom } from '@/types/quest';
import type { PipelineStep } from '@/types';

export interface AppendQuestEventInput {
  conversation_id: string;
  document_id?: string | null;
  session_id?: string | null;
  user_id: string;
  room: QuestRoom;
  event_key: string;
  level: QuestEventLevel;
  status: QuestEventStatus;
  message: string;
  metadata?: Record<string, unknown>;
}

export function mapPipelineStepToRoom(step?: PipelineStep): QuestRoom {
  if (!step) return 'library';

  if (step === 'research_intelligence' || step === 'strategist') {
    return 'hypothesis';
  }

  return 'library';
}

interface SupabaseLikeError {
  code?: string;
  message?: string;
  details?: string | null;
  hint?: string | null;
}

function normalizeErrorText(error: SupabaseLikeError): string {
  return `${error.code || ''} ${error.message || ''} ${error.details || ''} ${error.hint || ''}`.toLowerCase();
}

export function isQuestEventsUnavailableError(error: SupabaseLikeError): boolean {
  const text = normalizeErrorText(error);
  const mentionsQuestEvents = text.includes('quest_events');
  const missingTableSignals =
    text.includes('schema cache') ||
    text.includes('could not find the table') ||
    text.includes('does not exist') ||
    text.includes('undefined table') ||
    text.includes('pgrst204') ||
    text.includes('42p01');

  return mentionsQuestEvents && missingTableSignals;
}

let questEventsUnavailable = false;
let unavailableLogged = false;

export async function appendQuestEvent(
  supabase: SupabaseClient,
  input: AppendQuestEventInput
): Promise<void> {
  if (questEventsUnavailable) return;

  try {
    const { error } = await supabase.from('quest_events').insert({
      conversation_id: input.conversation_id,
      document_id: input.document_id ?? null,
      session_id: input.session_id ?? null,
      user_id: input.user_id,
      room: input.room,
      event_key: input.event_key,
      level: input.level,
      status: input.status,
      message: input.message,
      metadata: input.metadata ?? {},
    });

    if (error) {
        if (isQuestEventsUnavailableError(error)) {
        questEventsUnavailable = true;
        if (!unavailableLogged) {
          unavailableLogged = true;
          logger.warn('quest_events table unavailable; run apps/web/supabase/004_quest_events_and_domain.sql to enable event writes');
        }
        return;
      }

      logger.warn('Quest event insert failed', {
        conversationId: input.conversation_id,
        eventKey: input.event_key,
        error: error.message,
      });
    }
  } catch (error) {
    logger.warn('Quest event insert crashed', {
      conversationId: input.conversation_id,
      eventKey: input.event_key,
      error: error instanceof Error ? error.message : String(error),
    });
  }
}
