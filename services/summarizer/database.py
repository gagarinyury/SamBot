"""Database operations for summarizer service."""

import asyncpg
from typing import Optional, Dict, Any
import structlog

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
                SELECT
                    oc.id,
                    oc.original_url as url,
                    oc.raw_content,
                    oc.metadata,
                    sc.summary as summary
                FROM original_content oc
                LEFT JOIN LATERAL (
                    SELECT summary
                    FROM summaries_cache
                    WHERE content_id = oc.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) sc ON true
                WHERE oc.id = $1
                """,
                content_id
            )

            if not row:
                return None

            # metadata is already a dict (asyncpg auto-decodes JSONB)
            metadata = row['metadata']
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)

            return {
                'id': row['id'],
                'url': row['url'],
                'raw_content': row['raw_content'],
                'metadata': metadata,
                'summary': row['summary']
            }

    async def save_summary(self, content_id: int, summary: str) -> bool:
        """Save summary for content."""
        async with self.pool.acquire() as conn:
            # Get content language from original_content
            lang_row = await conn.fetchrow(
                "SELECT content_language FROM original_content WHERE id = $1",
                content_id
            )
            language = lang_row['content_language'] if lang_row else 'ru'

            # Insert or update in summaries_cache table
            await conn.execute(
                """
                INSERT INTO summaries_cache (
                    content_id, summary, summary_language, summary_length, created_at
                )
                VALUES ($1, $2, $3, 'medium', NOW())
                ON CONFLICT (content_id, summary_language, summary_length, prompt_id)
                DO UPDATE SET
                    summary = EXCLUDED.summary,
                    updated_at = NOW(),
                    access_count = summaries_cache.access_count + 1,
                    last_accessed_at = NOW()
                """,
                content_id,
                summary,
                language
            )
            logger.info("summary_saved", content_id=content_id, length=len(summary))
            return True


# Global database instance
db = Database()
