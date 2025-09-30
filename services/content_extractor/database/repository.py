"""
Data repository for content storage.
"""

import asyncpg
import hashlib
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ContentRepository:
    """Repository for content and chunks."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @staticmethod
    def generate_hash(text: str) -> str:
        """Generate SHA256 hash."""
        return hashlib.sha256(text.encode()).hexdigest()

    async def store_content(
        self,
        url: str,
        content: str,
        content_type: str,
        metadata: Dict,
        extraction_method: str,
        user_id: Optional[int] = None
    ) -> int:
        """Store original content."""
        url_hash = self.generate_hash(url)
        content_hash = self.generate_hash(content)

        async with self.pool.acquire() as conn:
            # Check if content already exists
            existing = await conn.fetchrow(
                "SELECT id FROM original_content WHERE content_hash = $1",
                content_hash
            )

            if existing:
                logger.info(f"Content already exists: {existing['id']}")
                return existing['id']

            # Insert new content
            content_id = await conn.fetchval(
                """
                INSERT INTO original_content (
                    url_hash, original_url, content_type, content_hash,
                    raw_content, content_language, metadata,
                    extraction_method, content_length, created_by_user_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                url_hash, url, content_type, content_hash,
                content, metadata.get('language'), json.dumps(metadata),
                extraction_method, len(content), user_id
            )

            logger.info(f"Stored content: {content_id}")
            return content_id

    async def store_chunks(
        self,
        content_id: int,
        chunks: List[Dict],
        strategy_name: str,
        strategy_metadata: Dict
    ) -> int:
        """Store content chunks."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Store chunking strategy
                await conn.execute(
                    """
                    INSERT INTO chunking_strategies (
                        content_id, strategy_name, total_chunks, metadata
                    ) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (content_id) DO UPDATE
                    SET strategy_name = $2, total_chunks = $3, metadata = $4
                    """,
                    content_id, strategy_name, len(chunks), json.dumps(strategy_metadata)
                )

                # Store chunks
                for chunk in chunks:
                    await conn.execute(
                        """
                        INSERT INTO content_chunks (
                            content_id, chunk_text, chunk_index,
                            start_timestamp, end_timestamp,
                            chunk_length, chunk_tokens
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        content_id,
                        chunk.get('chunk_text'),
                        chunk.get('chunk_index'),
                        chunk.get('start_timestamp'),
                        chunk.get('end_timestamp'),
                        chunk.get('chunk_length'),
                        chunk.get('chunk_tokens')
                    )

                logger.info(f"Stored {len(chunks)} chunks for content {content_id}")
                return len(chunks)

    async def get_content(self, content_id: int) -> Optional[Dict]:
        """Get content by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id, original_url, content_type, raw_content,
                    content_language, metadata, extraction_method,
                    created_at
                FROM original_content
                WHERE id = $1
                """,
                content_id
            )

            if not row:
                return None

            return dict(row)

    async def get_chunks(self, content_id: int) -> List[Dict]:
        """Get chunks for content."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    chunk_index, chunk_text, start_timestamp, end_timestamp,
                    chunk_length, chunk_tokens
                FROM content_chunks
                WHERE content_id = $1
                ORDER BY chunk_index
                """,
                content_id
            )

            return [dict(row) for row in rows]