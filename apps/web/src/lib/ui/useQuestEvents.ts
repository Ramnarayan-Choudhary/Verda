'use client';

import { useEffect, useState } from 'react';
import type { QuestEvent } from '@/types/quest';

interface UseQuestEventsOptions {
  enabled?: boolean;
  pollMs?: number;
  limit?: number;
}

interface UseQuestEventsResult {
  events: QuestEvent[];
  error: string | null;
  isLoading: boolean;
}

export function useQuestEvents(
  conversationId: string | null,
  options: UseQuestEventsOptions = {}
): UseQuestEventsResult {
  const { enabled = true, pollMs = 2500, limit = 120 } = options;
  const [events, setEvents] = useState<QuestEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [tableUnavailable, setTableUnavailable] = useState(false);

  useEffect(() => {
    if (!enabled || !conversationId) {
      setEvents([]);
      setError(null);
      setIsLoading(false);
      setTableUnavailable(false);
      return;
    }

    let cancelled = false;

    const fetchEvents = async () => {
      try {
        if (!cancelled) setIsLoading(true);
        const res = await fetch(`/api/quest-events?conversation_id=${conversationId}&limit=${limit}`, {
          cache: 'no-store',
        });

        const unavailableFlag = res.headers.get('x-quest-events-unavailable') === '1';
        if (!cancelled) {
          if (unavailableFlag && !tableUnavailable) {
            setTableUnavailable(true);
          } else if (!unavailableFlag && tableUnavailable) {
            setTableUnavailable(false);
          }
        }

        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as { error?: string };
          throw new Error(body.error || 'Failed to load quest events');
        }

        const data = (await res.json()) as QuestEvent[];
        if (!cancelled) {
          setEvents(Array.isArray(data) ? data : []);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load quest events');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void fetchEvents();
    const intervalMs = tableUnavailable ? 60000 : pollMs;
    const timer = window.setInterval(fetchEvents, intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [conversationId, enabled, limit, pollMs, tableUnavailable]);

  return { events, error, isLoading };
}
