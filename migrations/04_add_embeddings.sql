-- Migration: Add vector embeddings support
-- Date: 2025-09-30
-- Description: Add embedding column and indexes for RAG semantic search

-- Add embedding column to original_content (768 dimensions for nomic-embed-text)
ALTER TABLE original_content
ADD COLUMN IF NOT EXISTS embedding vector(768);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS original_content_embedding_idx
ON original_content
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Add embedding metadata
ALTER TABLE original_content
ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100),
ADD COLUMN IF NOT EXISTS embedding_created_at TIMESTAMP;

COMMENT ON COLUMN original_content.embedding IS 'Text embedding vector (768-dim nomic-embed-text)';
COMMENT ON COLUMN original_content.embedding_model IS 'Name of embedding model used';
COMMENT ON COLUMN original_content.embedding_created_at IS 'When embedding was generated';
