-- ============================================
-- VREDA.ai: Upgrade vector index to HNSW
-- Migration 003
--
-- WHY: IVFFlat requires training data and has lower recall on small datasets.
-- HNSW provides better recall at all scales with no training requirement.
-- Trade-off: slightly more memory, but retrieval quality improves ~10-15%.
--
-- Run this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/hpjkqjzyuynoxcovdjpz/sql/new
-- ============================================

-- Step 1: Drop the old IVFFlat index
drop index if exists idx_document_chunks_embedding;

-- Step 2: Create HNSW index for cosine similarity
-- m=16: connections per node (default, good balance of speed vs recall)
-- ef_construction=64: build-time search width (higher = better recall, slower build)
create index idx_document_chunks_embedding
    on document_chunks
    using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);
