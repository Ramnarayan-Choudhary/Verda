-- ============================================
-- VREDA.ai: Quest Domain + Quest Events
-- Migration 004
-- ============================================

-- 1) Persist conversation domain for multi-domain research UX
alter table conversations
  add column if not exists domain text not null default 'ai_ml';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'conversations_domain_check'
  ) then
    alter table conversations
      add constraint conversations_domain_check
      check (domain in ('ai_ml', 'comp_bio', 'simulation', 'drug_discovery'));
  end if;
end $$;

-- 2) Quest events timeline for war room agent activity
create table if not exists quest_events (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  document_id uuid references documents(id) on delete cascade,
  session_id uuid,
  user_id uuid not null references auth.users(id) on delete cascade,
  room text not null check (room in ('library', 'hypothesis', 'experiment', 'results', 'writing')),
  event_key text not null,
  level text not null check (level in ('info', 'warn', 'success', 'error')),
  status text not null check (status in ('active', 'done', 'warning', 'error')),
  message text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_quest_events_conversation_created
  on quest_events(conversation_id, created_at desc);

create index if not exists idx_quest_events_user_created
  on quest_events(user_id, created_at desc);

-- 3) RLS policies (append-only for clients)
alter table quest_events enable row level security;

create policy "Users can view own quest events"
  on quest_events for select
  using (auth.uid() = user_id);

create policy "Users can create own quest events"
  on quest_events for insert
  with check (auth.uid() = user_id);
