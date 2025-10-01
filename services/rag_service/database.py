"""Database operations for RAG service."""

import asyncpg
from typing import Optional, List, Dict, Any
import structlog
import numpy as np

from config import settings

logger = structlog.get_logger()


class Database:
    """Database connection and operations."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create database connection pool."""
        self.pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=2,
            max_size=10
        )
        logger.info("database_connected")

    async def disconnect(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("database_disconnected")

    async def get_content(self, content_id: int) -> Optional[Dict[str, Any]]:
        """Get content by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, original_url, raw_content, metadata, embedding
                FROM original_content
                WHERE id = $1
                """,
                content_id
            )

            if not row:
                return None

            return {
                'id': row['id'],
                'url': row['original_url'],
                'raw_content': row['raw_content'],
                'metadata': row['metadata'],
                'has_embedding': row['embedding'] is not None
            }

    async def save_embedding(
        self,
        content_id: int,
        embedding: List[float],
        model: str
    ) -> bool:
        """Save embedding for content."""
        async with self.pool.acquire() as conn:
            # Convert list to pgvector format
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'

            await conn.execute(
                """
                UPDATE original_content
                SET
                    embedding = $1::vector,
                    embedding_model = $2,
                    embedding_created_at = NOW()
                WHERE id = $3
                """,
                embedding_str,
                model,
                content_id
            )
            logger.info("embedding_saved", content_id=content_id, model=model)
            return True

    async def semantic_search(
        self,
        query_embedding: List[float],
        limit: int = 3,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar content using vector similarity.

        Args:
            query_embedding: Query vector
            limit: Max results to return
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of similar content with similarity scores
        """
        async with self.pool.acquire() as conn:
            # Convert embedding to pgvector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

            rows = await conn.fetch(
                """
                SELECT
                    id,
                    original_url,
                    raw_content,
                    metadata,
                    1 - (embedding <=> $1::vector) as similarity
                FROM original_content
                WHERE
                    embedding IS NOT NULL
                    AND 1 - (embedding <=> $1::vector) >= $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                embedding_str,
                min_similarity,
                limit
            )

            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'url': row['original_url'],
                    'content': row['raw_content'],
                    'metadata': row['metadata'],
                    'similarity': float(row['similarity'])
                })

            logger.info(
                "semantic_search_completed",
                results_count=len(results),
                min_similarity=min_similarity
            )

            return results


# Global database instance
db = Database()
