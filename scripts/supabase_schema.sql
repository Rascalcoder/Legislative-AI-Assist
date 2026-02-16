-- Legislative AI Assist - Supabase Schema
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New Query)

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 1. DOCUMENTS table (document metadata)
-- ============================================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'legal',
    jurisdiction TEXT,                          -- 'SK', 'EU', or NULL
    source_id TEXT,                             -- references sources.json id
    language TEXT NOT NULL DEFAULT 'en',
    upload_date TIMESTAMPTZ DEFAULT NOW(),
    size_bytes INTEGER,
    status TEXT DEFAULT 'processing',           -- processing, processed, error
    chunk_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. CHUNKS table (document chunks with embeddings + FTS)
-- ============================================================
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', content)
    ) STORED,
    embedding VECTOR(1536),                    -- text-embedding-3-large (dimensions=1536)
    language TEXT NOT NULL DEFAULT 'en',
    jurisdiction TEXT,                          -- 'SK', 'EU'
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. CONVERSATIONS table
-- ============================================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    language TEXT DEFAULT 'en',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================================
-- 4. MESSAGES table (conversation history)
-- ============================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]'::jsonb,
    confidence FLOAT,
    language TEXT,
    token_count INTEGER,
    model_used TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. AUDIT LOG table (cost tracking, debugging)
-- ============================================================
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,                       -- 'llm_call', 'search', 'upload', 'error'
    model TEXT,
    provider TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd FLOAT,
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Vector similarity search (HNSW for better performance on small datasets)
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops);

-- Full-text search index
CREATE INDEX idx_chunks_fts ON chunks USING GIN (content_tsv);

-- Filter indexes
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_jurisdiction ON chunks(jurisdiction);
CREATE INDEX idx_chunks_language ON chunks(language);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_jurisdiction ON documents(jurisdiction);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- ============================================================
-- HYBRID SEARCH RPC FUNCTION (vector + FTS + RRF fusion)
-- ============================================================
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding VECTOR(1536),
    query_text TEXT,
    match_count INTEGER DEFAULT 5,
    vector_weight FLOAT DEFAULT 0.6,
    fts_weight FLOAT DEFAULT 0.4,
    rrf_k INTEGER DEFAULT 60,
    filter_jurisdiction TEXT DEFAULT NULL,
    filter_language TEXT DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    jurisdiction TEXT,
    language TEXT,
    metadata JSONB,
    vector_rank BIGINT,
    fts_rank BIGINT,
    rrf_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH vector_results AS (
        SELECT
            c.id,
            c.document_id,
            c.content,
            c.jurisdiction,
            c.language,
            c.metadata,
            ROW_NUMBER() OVER (
                ORDER BY c.embedding <=> query_embedding
            ) AS rank
        FROM chunks c
        WHERE (filter_jurisdiction IS NULL OR c.jurisdiction = filter_jurisdiction)
          AND (filter_language IS NULL OR c.language = filter_language)
          AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count * 3
    ),
    fts_results AS (
        SELECT
            c.id,
            c.document_id,
            c.content,
            c.jurisdiction,
            c.language,
            c.metadata,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank(c.content_tsv, websearch_to_tsquery('simple', query_text)) DESC
            ) AS rank
        FROM chunks c
        WHERE c.content_tsv @@ websearch_to_tsquery('simple', query_text)
          AND (filter_jurisdiction IS NULL OR c.jurisdiction = filter_jurisdiction)
          AND (filter_language IS NULL OR c.language = filter_language)
        ORDER BY ts_rank(c.content_tsv, websearch_to_tsquery('simple', query_text)) DESC
        LIMIT match_count * 3
    ),
    combined AS (
        SELECT
            COALESCE(v.id, f.id) AS chunk_id,
            COALESCE(v.document_id, f.document_id) AS document_id,
            COALESCE(v.content, f.content) AS content,
            COALESCE(v.jurisdiction, f.jurisdiction) AS jurisdiction,
            COALESCE(v.language, f.language) AS language,
            COALESCE(v.metadata, f.metadata) AS metadata,
            COALESCE(v.rank, 999) AS vector_rank,
            COALESCE(f.rank, 999) AS fts_rank,
            (
                vector_weight * (1.0 / (rrf_k + COALESCE(v.rank, 999))) +
                fts_weight * (1.0 / (rrf_k + COALESCE(f.rank, 999)))
            ) AS rrf_score
        FROM vector_results v
        FULL OUTER JOIN fts_results f ON v.id = f.id
    )
    SELECT
        combined.chunk_id,
        combined.document_id,
        combined.content,
        combined.jurisdiction,
        combined.language,
        combined.metadata,
        combined.vector_rank,
        combined.fts_rank,
        combined.rrf_score
    FROM combined
    ORDER BY combined.rrf_score DESC
    LIMIT match_count;
END;
$$;
