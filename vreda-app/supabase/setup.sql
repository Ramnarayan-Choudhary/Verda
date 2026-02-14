-- ============================================
-- VREDA.ai Database Setup
-- Run this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/hpjkqjzyuynoxcovdjpz/sql/new
-- ============================================

-- Step 1: Enable pgvector extension
create extension if not exists vector;

-- Step 2: Conversations table
create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  title text default 'New Research Quest',
  created_at timestamptz default now()
);

-- Step 3: Messages table
create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id) on delete cascade,
  role text check (role in ('user', 'assistant', 'system')),
  content text,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

-- Step 4: Documents table (uploaded PDFs)
create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  conversation_id uuid references conversations(id) on delete cascade,
  filename text,
  storage_path text,
  status text default 'processing',
  created_at timestamptz default now()
);

-- Step 5: Document chunks with vector embeddings
create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade,
  content text,
  embedding vector(768),
  chunk_index int,
  created_at timestamptz default now()
);

-- Step 6: Create index for fast similarity search
create index if not exists idx_document_chunks_embedding
  on document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Step 7: Similarity search function
create or replace function match_chunks(
  query_embedding vector(768),
  match_count int default 5,
  filter_doc_id uuid default null
)
returns table (id uuid, content text, similarity float)
language plpgsql as $$
begin
  return query
  select dc.id, dc.content, 1 - (dc.embedding <=> query_embedding) as similarity
  from document_chunks dc
  where (filter_doc_id is null or dc.document_id = filter_doc_id)
  order by dc.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Step 8: Enable Row Level Security
alter table conversations enable row level security;
alter table messages enable row level security;
alter table documents enable row level security;
alter table document_chunks enable row level security;

-- Step 9: RLS Policies
-- Conversations: users can only see their own
create policy "Users can view own conversations"
  on conversations for select
  using (auth.uid() = user_id);

create policy "Users can create conversations"
  on conversations for insert
  with check (auth.uid() = user_id);

create policy "Users can delete own conversations"
  on conversations for delete
  using (auth.uid() = user_id);

-- Messages: users can access messages in their conversations
create policy "Users can view messages in own conversations"
  on messages for select
  using (
    conversation_id in (
      select id from conversations where user_id = auth.uid()
    )
  );

create policy "Users can create messages in own conversations"
  on messages for insert
  with check (
    conversation_id in (
      select id from conversations where user_id = auth.uid()
    )
  );

-- Documents: users can only access their own
create policy "Users can view own documents"
  on documents for select
  using (auth.uid() = user_id);

create policy "Users can upload documents"
  on documents for insert
  with check (auth.uid() = user_id);

-- Document chunks: accessible via document ownership
create policy "Users can view chunks of own documents"
  on document_chunks for select
  using (
    document_id in (
      select id from documents where user_id = auth.uid()
    )
  );

create policy "Users can create chunks for own documents"
  on document_chunks for insert
  with check (
    document_id in (
      select id from documents where user_id = auth.uid()
    )
  );

-- Step 10: Create storage bucket for research papers
-- NOTE: Run this manually in Supabase Dashboard > Storage > New Bucket
-- Name: research-papers
-- Public: false
-- File size limit: 50MB
-- Allowed MIME types: application/pdf
