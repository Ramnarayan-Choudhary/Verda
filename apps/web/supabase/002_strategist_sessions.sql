-- ============================================
-- VREDA.ai: Strategist Room Sessions
-- Migration 002
-- ============================================

-- Stores the full multi-agent state for each paper analysis session.
-- The state JSONB column contains the entire StrategistRoomState object.
create table if not exists strategist_sessions (
    id uuid primary key,
    document_id uuid references documents(id) on delete cascade,
    conversation_id uuid references conversations(id) on delete cascade,
    user_id uuid references auth.users(id) on delete cascade,
    state jsonb not null default '{}',
    phase text not null default 'idle',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Fast lookup by conversation (used when loading chat page)
create index if not exists idx_strategist_sessions_conversation
    on strategist_sessions(conversation_id);

-- Fast lookup by document (used when re-running analysis)
create index if not exists idx_strategist_sessions_document
    on strategist_sessions(document_id);

-- Row Level Security
alter table strategist_sessions enable row level security;

create policy "Users can view own strategist sessions"
    on strategist_sessions for select
    using (auth.uid() = user_id);

create policy "Users can create strategist sessions"
    on strategist_sessions for insert
    with check (auth.uid() = user_id);

create policy "Users can update own strategist sessions"
    on strategist_sessions for update
    using (auth.uid() = user_id);
