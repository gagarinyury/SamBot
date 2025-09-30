-- ========================================
-- SamBot 2.0 RAG System Tables
-- Content chunking and embeddings for semantic search
-- ========================================

-- ========================================
-- CONTENT CHUNKING FOR RAG
-- ========================================

-- Content chunks for RAG (splitting long content into manageable pieces)
CREATE TABLE content_chunks (
    id SERIAL PRIMARY KEY,
    content_id INTEGER NOT NULL REFERENCES original_content(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,

    -- Video-specific fields (timestamps for navigation)
    start_timestamp INTEGER,  -- Start time in seconds for video content
    end_timestamp INTEGER,    -- End time in seconds for video content

    -- Metadata
    chunk_length INTEGER NOT NULL,  -- Character count of chunk
    chunk_tokens INTEGER,           -- Token count estimate

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(content_id, chunk_index)
);

-- ========================================
-- EMBEDDINGS FOR SEMANTIC SEARCH
-- ========================================

-- Embeddings storage using pgvector
CREATE TABLE content_embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER NOT NULL REFERENCES content_chunks(id) ON DELETE CASCADE,

    -- Vector embedding (1536 dimensions for text-embedding-3-small)
    -- Adjust dimension based on your embedding model
    embedding vector(1536) NOT NULL,

    -- Metadata about embedding generation
    model_name VARCHAR(255) DEFAULT 'docker-model-runner',
    model_version VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(chunk_id)
);

-- ========================================
-- RAG QUERIES LOG (for analytics)
-- ========================================

-- Log RAG queries for analytics and improvement
CREATE TABLE rag_queries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content_id INTEGER NOT NULL REFERENCES original_content(id) ON DELETE CASCADE,

    query_text TEXT NOT NULL,
    query_embedding vector(1536),

    -- Retrieved chunks
    retrieved_chunk_ids INTEGER[],
    top_k INTEGER DEFAULT 5,

    -- Query performance metrics
    search_time_ms INTEGER,
    chunks_found INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- CHUNKING STRATEGIES
-- ========================================

-- Track which chunking strategy was used for each content
CREATE TABLE chunking_strategies (
    id SERIAL PRIMARY KEY,
    content_id INTEGER NOT NULL REFERENCES original_content(id) ON DELETE CASCADE,

    strategy_name VARCHAR(100) NOT NULL,  -- 'fixed_size', 'chapter_based', 'semantic'
    chunk_size INTEGER,                    -- Tokens per chunk
    chunk_overlap INTEGER,                 -- Overlap between chunks in tokens

    total_chunks INTEGER NOT NULL,
    metadata JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(content_id)
);

-- ========================================
-- INDEXES FOR PERFORMANCE
-- ========================================

-- Vector similarity search index (IVFFlat algorithm)
-- Lists parameter should be sqrt(total_rows) for optimal performance
CREATE INDEX idx_embeddings_vector ON content_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Regular indexes for filtering
CREATE INDEX idx_chunks_content_id ON content_chunks(content_id);
CREATE INDEX idx_chunks_content_chunk_idx ON content_chunks(content_id, chunk_index);
CREATE INDEX idx_embeddings_chunk_id ON content_embeddings(chunk_id);
CREATE INDEX idx_rag_queries_content_id ON rag_queries(content_id);
CREATE INDEX idx_rag_queries_user_id ON rag_queries(user_id);
CREATE INDEX idx_rag_queries_created_at ON rag_queries(created_at);

-- ========================================
-- HELPER FUNCTIONS
-- ========================================

-- Function to calculate cosine similarity between vectors
CREATE OR REPLACE FUNCTION cosine_similarity(
    embedding1 vector(1536),
    embedding2 vector(1536)
) RETURNS FLOAT AS $$
BEGIN
    RETURN 1 - (embedding1 <=> embedding2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to find similar chunks using vector search
CREATE OR REPLACE FUNCTION find_similar_chunks(
    query_embedding vector(1536),
    target_content_id INTEGER,
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 5
) RETURNS TABLE (
    chunk_id INTEGER,
    chunk_text TEXT,
    similarity FLOAT,
    start_timestamp INTEGER,
    end_timestamp INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.chunk_text,
        1 - (e.embedding <=> query_embedding) AS similarity,
        c.start_timestamp,
        c.end_timestamp
    FROM content_chunks c
    JOIN content_embeddings e ON c.id = e.chunk_id
    WHERE c.content_id = target_content_id
      AND (1 - (e.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- STATISTICS VIEW
-- ========================================

-- View for RAG system statistics
CREATE OR REPLACE VIEW rag_stats AS
SELECT
    COUNT(DISTINCT c.content_id) as total_contents_with_chunks,
    COUNT(c.id) as total_chunks,
    COUNT(e.id) as total_embeddings,
    AVG(c.chunk_length) as avg_chunk_length,
    AVG(rq.chunks_found) as avg_chunks_found_per_query,
    COUNT(DISTINCT rq.id) as total_rag_queries
FROM content_chunks c
LEFT JOIN content_embeddings e ON c.id = e.chunk_id
LEFT JOIN rag_queries rq ON c.content_id = rq.content_id;

-- ========================================
-- COMMENTS FOR DOCUMENTATION
-- ========================================

COMMENT ON TABLE content_chunks IS 'Text chunks for RAG semantic search';
COMMENT ON TABLE content_embeddings IS 'Vector embeddings for chunks using pgvector';
COMMENT ON TABLE rag_queries IS 'Log of RAG queries for analytics and improvement';
COMMENT ON TABLE chunking_strategies IS 'Record of chunking strategy used for each content';
COMMENT ON FUNCTION find_similar_chunks IS 'Find similar chunks using cosine similarity search';
COMMENT ON VIEW rag_stats IS 'Statistics about RAG system usage and performance';