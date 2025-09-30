"""
PostgreSQL async connection handler.
"""

import asyncpg
import logging
from typing import Optional
import os

logger = logging.getLogger(__name__)

_connection_pool: Optional[asyncpg.Pool] = None


async def get_db_connection() -> asyncpg.Pool:
    """Get or create database connection pool."""
    global _connection_pool

    if _connection_pool is None:
        database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://sambot:sambot_secure_pass_change_me@postgres:5432/sambot_v2'
        )

        try:
            _connection_pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    return _connection_pool


async def close_db_connection():
    """Close database connection pool."""
    global _connection_pool

    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None
        logger.info("Database connection pool closed")