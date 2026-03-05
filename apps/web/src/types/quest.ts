export type QuestDomain = 'ai_ml' | 'comp_bio' | 'simulation' | 'drug_discovery';

export type QuestRoom = 'library' | 'hypothesis' | 'experiment' | 'results' | 'writing';

export type QuestEventLevel = 'info' | 'warn' | 'success' | 'error';

export type QuestEventStatus = 'active' | 'done' | 'warning' | 'error';

export interface QuestEvent {
  id: string;
  conversation_id: string;
  document_id: string | null;
  session_id: string | null;
  user_id: string;
  room: QuestRoom;
  event_key: string;
  level: QuestEventLevel;
  status: QuestEventStatus;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}
