"""Database operations for Content Extractor service."""

import asyncpg
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

from config import settings

logger = structlog.get_logger()


class Database:
    """Database handler for content extraction."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("database_connected", pool_size=self.pool.get_size())
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            raise

    async def disconnect(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("database_disconnected")

    async def check_cache(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Check if content already exists in database.

        Args:
            url: Original URL

        Returns:
            Content record if exists, None otherwise
        """
        url_hash = hashlib.sha256(url.encode()).hexdigest()

        query = """
            SELECT
                id,
                original_url,
                content_type,
                metadata,
                raw_content,
                audio_file_path,
                extraction_method,
                created_at,
                (SELECT COUNT(*) FROM content_chunks WHERE content_id = oc.id) as chunk_count
            FROM original_content oc
            WHERE url_hash = $1
        """

        try:
            row = await self.pool.fetchrow(query, url_hash)
            if row:
                logger.info("cache_hit", url_hash=url_hash[:16], content_id=row['id'])
                # Convert Record to dict, preserving JSON types
                result = {
                    'id': row['id'],
                    'url': row['original_url'],
                    'content_type': row['content_type'],
                    'metadata': row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata']),
                    'raw_content': row['raw_content'],
                    'audio_file_path': row['audio_file_path'],
                    'extraction_method': row['extraction_method'],
                    'created_at': row['created_at'],
                    'chunk_count': row['chunk_count']
                }
                return result
            return None
        except Exception as e:
            logger.error("cache_check_failed", error=str(e))
            raise

    async def save_content(
        self,
        url: str,
        content_type: str,
        metadata: Dict[str, Any],
        raw_content: Optional[str] = None,
        audio_file_path: Optional[str] = None,
        extraction_method: str = "yt-dlp",
        user_id: Optional[int] = None
    ) -> int:
        """
        Save extracted content to database.

        Returns:
            content_id
        """
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        # content_hash: use empty string hash if no content (to satisfy NOT NULL)
        content_hash = hashlib.sha256((raw_content or "").encode()).hexdigest()

        query = """
            INSERT INTO original_content (
                original_url,
                url_hash,
                content_hash,
                content_type,
                metadata,
                raw_content,
                audio_file_path,
                content_language,
                extraction_method,
                created_by_user_id,
                created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
        """

        try:
            content_id = await self.pool.fetchval(
                query,
                url,
                url_hash,
                content_hash,
                content_type,
                json.dumps(metadata),  # Convert dict to JSON string
                raw_content,
                audio_file_path,
                metadata.get('language'),
                extraction_method,
                user_id,
                datetime.utcnow()
            )

            logger.info(
                "content_saved",
                content_id=content_id,
                content_type=content_type,
                has_transcript=bool(raw_content),
                has_audio=bool(audio_file_path)
            )

            return content_id

        except Exception as e:
            logger.error("content_save_failed", error=str(e))
            raise

    async def save_chunks(
        self,
        content_id: int,
        chunks: List[Dict[str, Any]],
        strategy_name: str = "fixed_size_500"
    ) -> int:
        """
        Save content chunks to database.

        Returns:
            Number of chunks saved
        """
        # Save chunking strategy
        strategy_query = """
            INSERT INTO chunking_strategies (
                content_id,
                strategy_name,
                chunk_size,
                chunk_overlap,
                total_chunks,
                created_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """

        await self.pool.execute(
            strategy_query,
            content_id,
            strategy_name,
            settings.DEFAULT_CHUNK_SIZE,
            settings.DEFAULT_CHUNK_OVERLAP,
            len(chunks),
            datetime.utcnow()
        )

        # Save chunks
        chunk_query = """
            INSERT INTO content_chunks (
                content_id,
                chunk_text,
                chunk_index,
                start_timestamp,
                end_timestamp,
                chunk_length,
                chunk_tokens,
                created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for chunk in chunks:
                        await conn.execute(
                            chunk_query,
                            content_id,
                            chunk['text'],
                            chunk['index'],
                            chunk.get('start_timestamp'),
                            chunk.get('end_timestamp'),
                            len(chunk['text']),
                            chunk.get('tokens', 0),
                            datetime.utcnow()
                        )

            logger.info("chunks_saved", content_id=content_id, count=len(chunks))
            return len(chunks)

        except Exception as e:
            logger.error("chunks_save_failed", error=str(e), content_id=content_id)
            raise

    async def update_audio_processed(self, content_id: int):
        """Mark audio as processed (for cleanup)."""
        query = """
            UPDATE original_content
            SET audio_processed = TRUE,
                audio_processed_at = $1
            WHERE id = $2
        """

        try:
            await self.pool.execute(query, datetime.utcnow(), content_id)
            logger.info("audio_marked_processed", content_id=content_id)
        except Exception as e:
            logger.error("audio_update_failed", error=str(e), content_id=content_id)
            raise


# Global database instance
db = Database()