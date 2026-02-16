-- Fase 0: pgvector setup for semantic search
-- Requires pgvector >= 0.5.0 for HNSW index support

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE paper_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  section_title TEXT,
  page_number INTEGER,
  embedding VECTOR(1024),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunks_embedding ON paper_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_chunks_source ON paper_chunks(source_id);
CREATE INDEX idx_chunks_metadata ON paper_chunks USING GIN(metadata);

-- RLS
ALTER TABLE paper_chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON paper_chunks FOR ALL USING (true);

-- RPC for vector similarity search
CREATE OR REPLACE FUNCTION match_chunks(
  query_embedding VECTOR(1024),
  match_threshold FLOAT DEFAULT 0.7,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  source_id UUID,
  content TEXT,
  section_title TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    pc.id,
    pc.source_id,
    pc.content,
    pc.section_title,
    1 - (pc.embedding <=> query_embedding) AS similarity
  FROM paper_chunks pc
  WHERE 1 - (pc.embedding <=> query_embedding) > match_threshold
  ORDER BY pc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
