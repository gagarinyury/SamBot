#!/usr/bin/env python3
"""
SamBot 2.0 - SQLite to PostgreSQL Migration Script

This script migrates data from the old SamBot SQLite database
to the new PostgreSQL + pgvector database.

Usage:
    python scripts/migrate_from_sqlite.py --sqlite-path ../SamBot/database/sambot.db
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any
import aiosqlite
import asyncpg
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handles migration from SQLite to PostgreSQL."""

    def __init__(self, sqlite_path: str, postgres_url: str):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.stats = {
            'users': 0,
            'original_content': 0,
            'summaries_cache': 0,
            'usage_stats': 0,
            'errors': 0
        }

    async def connect(self):
        """Establish database connections."""
        logger.info(f"Connecting to SQLite: {self.sqlite_path}")
        self.sqlite_conn = await aiosqlite.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = aiosqlite.Row

        logger.info(f"Connecting to PostgreSQL...")
        self.pg_conn = await asyncpg.connect(self.postgres_url)

    async def close(self):
        """Close database connections."""
        if hasattr(self, 'sqlite_conn'):
            await self.sqlite_conn.close()
        if hasattr(self, 'pg_conn'):
            await self.pg_conn.close()

    async def migrate_users(self):
        """Migrate users table."""
        logger.info("Migrating users...")

        async with self.sqlite_conn.execute("SELECT * FROM users") as cursor:
            users = await cursor.fetchall()

        for user in users:
            try:
                await self.pg_conn.execute("""
                    INSERT INTO users (
                        id, telegram_id, username, first_name, last_name,
                        language_code, subscription_type, subscription_expires_at,
                        total_requests, created_at, updated_at, is_blocked,
                        country_code, timezone
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                    ) ON CONFLICT (telegram_id) DO NOTHING
                """,
                    user['id'], user['telegram_id'], user['username'],
                    user['first_name'], user['last_name'], user['language_code'],
                    user['subscription_type'], user['subscription_expires_at'],
                    user['total_requests'], user['created_at'], user['updated_at'],
                    user['is_blocked'], user.get('country_code', 'FR'),
                    user.get('timezone', 'Europe/Paris')
                )
                self.stats['users'] += 1
            except Exception as e:
                logger.error(f"Error migrating user {user['telegram_id']}: {e}")
                self.stats['errors'] += 1

        # Update sequence
        await self.pg_conn.execute("""
            SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1), true)
        """)

        logger.info(f"Migrated {self.stats['users']} users")

    async def migrate_original_content(self):
        """Migrate original_content table."""
        logger.info("Migrating original content...")

        async with self.sqlite_conn.execute("SELECT * FROM original_content") as cursor:
            contents = await cursor.fetchall()

        for content in contents:
            try:
                await self.pg_conn.execute("""
                    INSERT INTO original_content (
                        id, url_hash, original_url, content_type, content_hash,
                        raw_content, content_language, metadata, extraction_method,
                        content_length, created_by_user_id, created_at, updated_at,
                        access_count, last_accessed_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12, $13, $14, $15
                    ) ON CONFLICT (content_hash) DO NOTHING
                """,
                    content['id'], content['url_hash'], content['original_url'],
                    content['content_type'], content['content_hash'],
                    content['raw_content'], content['content_language'],
                    content['metadata'], content['extraction_method'],
                    content['content_length'], content['created_by_user_id'],
                    content['created_at'], content['updated_at'],
                    content['access_count'], content['last_accessed_at']
                )
                self.stats['original_content'] += 1
            except Exception as e:
                logger.error(f"Error migrating content {content['id']}: {e}")
                self.stats['errors'] += 1

        # Update sequence
        await self.pg_conn.execute("""
            SELECT setval('original_content_id_seq', COALESCE((SELECT MAX(id) FROM original_content), 1), true)
        """)

        logger.info(f"Migrated {self.stats['original_content']} content items")

    async def migrate_summaries_cache(self):
        """Migrate summaries_cache table."""
        logger.info("Migrating summaries cache...")

        async with self.sqlite_conn.execute("SELECT * FROM summaries_cache") as cursor:
            summaries = await cursor.fetchall()

        for summary in summaries:
            try:
                await self.pg_conn.execute("""
                    INSERT INTO summaries_cache (
                        id, content_id, summary, summary_language, summary_length,
                        prompt_id, tokens_used, created_by_user_id,
                        created_at, updated_at, access_count, last_accessed_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                    ) ON CONFLICT DO NOTHING
                """,
                    summary['id'], summary['content_id'], summary['summary'],
                    summary['summary_language'], summary['summary_length'],
                    summary['prompt_id'], summary['tokens_used'],
                    summary['created_by_user_id'], summary['created_at'],
                    summary['updated_at'], summary['access_count'],
                    summary['last_accessed_at']
                )
                self.stats['summaries_cache'] += 1
            except Exception as e:
                logger.error(f"Error migrating summary {summary['id']}: {e}")
                self.stats['errors'] += 1

        # Update sequence
        await self.pg_conn.execute("""
            SELECT setval('summaries_cache_id_seq', COALESCE((SELECT MAX(id) FROM summaries_cache), 1), true)
        """)

        logger.info(f"Migrated {self.stats['summaries_cache']} summaries")

    async def migrate_usage_stats(self):
        """Migrate usage_stats table."""
        logger.info("Migrating usage stats...")

        async with self.sqlite_conn.execute("SELECT * FROM usage_stats") as cursor:
            stats = await cursor.fetchall()

        for stat in stats:
            try:
                await self.pg_conn.execute("""
                    INSERT INTO usage_stats (
                        id, user_id, date, requests_count, tokens_used, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6
                    ) ON CONFLICT (user_id, date) DO NOTHING
                """,
                    stat['id'], stat['user_id'], stat['date'],
                    stat['requests_count'], stat['tokens_used'],
                    stat['created_at']
                )
                self.stats['usage_stats'] += 1
            except Exception as e:
                logger.error(f"Error migrating usage stat {stat['id']}: {e}")
                self.stats['errors'] += 1

        # Update sequence
        await self.pg_conn.execute("""
            SELECT setval('usage_stats_id_seq', COALESCE((SELECT MAX(id) FROM usage_stats), 1), true)
        """)

        logger.info(f"Migrated {self.stats['usage_stats']} usage stats")

    async def migrate_all(self):
        """Run full migration."""
        try:
            await self.connect()

            logger.info("=" * 60)
            logger.info("Starting SamBot SQLite → PostgreSQL Migration")
            logger.info("=" * 60)

            await self.migrate_users()
            await self.migrate_original_content()
            await self.migrate_summaries_cache()
            await self.migrate_usage_stats()

            logger.info("=" * 60)
            logger.info("Migration completed!")
            logger.info("=" * 60)
            logger.info(f"Users migrated: {self.stats['users']}")
            logger.info(f"Content items migrated: {self.stats['original_content']}")
            logger.info(f"Summaries migrated: {self.stats['summaries_cache']}")
            logger.info(f"Usage stats migrated: {self.stats['usage_stats']}")
            logger.info(f"Errors encountered: {self.stats['errors']}")
            logger.info("=" * 60)

            return self.stats

        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise
        finally:
            await self.close()


async def main():
    parser = argparse.ArgumentParser(
        description='Migrate SamBot data from SQLite to PostgreSQL'
    )
    parser.add_argument(
        '--sqlite-path',
        default='../SamBot/database/sambot.db',
        help='Path to SQLite database file'
    )
    parser.add_argument(
        '--postgres-url',
        default='postgresql://sambot:sambot_secure_pass_change_me@localhost:5432/sambot_v2',
        help='PostgreSQL connection URL'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without making changes'
    )

    args = parser.parse_args()

    # Check if SQLite file exists
    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        logger.error(f"SQLite database not found: {sqlite_path}")
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # Run migration
    migrator = DatabaseMigrator(str(sqlite_path), args.postgres_url)
    stats = await migrator.migrate_all()

    # Exit with success code
    if stats['errors'] == 0:
        logger.info("✅ Migration completed successfully!")
        sys.exit(0)
    else:
        logger.warning(f"⚠️  Migration completed with {stats['errors']} errors")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())