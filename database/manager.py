"""
Database Manager for SamBot
Handles all database operations with existing SQLite schema.
"""

import aiosqlite
import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Async SQLite database manager for SamBot.
    Integrates with existing schema.sql structure.
    """
    
    def __init__(self, db_path: str = "database/sambot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._connection = None
        
    async def initialize(self):
        """Initialize database with schema if not exists."""
        try:
            # Create database file if not exists
            if not self.db_path.exists():
                logger.info("Creating new database...")
                await self._create_database()
                await self._load_initial_data()
            
            # Test connection
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                await db.commit()
                
            logger.info(f"Database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _create_database(self):
        """Create database schema from schema.sql."""
        schema_path = Path("database/schema.sql")
        if not schema_path.exists():
            raise FileNotFoundError("database/schema.sql not found")
            
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema_sql)
            await db.commit()
            
        logger.info("Database schema created successfully")
    
    async def _load_initial_data(self):
        """Load initial data from initial_data.sql if exists."""
        data_path = Path("database/initial_data.sql")
        if data_path.exists():
            with open(data_path, 'r', encoding='utf-8') as f:
                data_sql = f.read()
                
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(data_sql)
                await db.commit()
                
            logger.info("Initial data loaded successfully")

    # ========================================
    # CACHE METHODS FOR DEEPSEEK INTEGRATION
    # ========================================
    
    async def get_cached_summary(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached summary by content hash."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute("""
                    SELECT summary, summary_language, summary_length, tokens_used, created_at
                    FROM summaries_cache 
                    WHERE content_hash = ?
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (content_hash,))
                
                row = await cursor.fetchone()
                if row:
                    # Update access statistics
                    await db.execute("""
                        UPDATE summaries_cache 
                        SET access_count = access_count + 1,
                            last_accessed_at = CURRENT_TIMESTAMP
                        WHERE content_hash = ?
                    """, (content_hash,))
                    await db.commit()
                    
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get cached summary: {e}")
            return None
    
    async def cache_summary(
        self, 
        url_hash: str,
        original_url: str,
        content_type: str,
        content_hash: str,
        summary: str,
        summary_language: str,
        summary_length: str,
        tokens_used: int,
        created_by_user_id: Optional[int] = None,
        content_language: Optional[str] = None
    ):
        """Cache a summary in the database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO summaries_cache 
                    (url_hash, original_url, content_type, content_hash, content_language,
                     summary, summary_language, summary_length, tokens_used, created_by_user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    url_hash, original_url, content_type, content_hash, content_language,
                    summary, summary_language, summary_length, tokens_used, created_by_user_id
                ))
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to cache summary: {e}")
    
    async def get_prompt_template(
        self, 
        content_type: str, 
        language: str, 
        length: str = "medium"
    ) -> Optional[str]:
        """Get prompt template from database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Try to find specific template
                cursor = await db.execute("""
                    SELECT template FROM prompt_templates 
                    WHERE content_type = ? AND language = ? AND is_active = 1
                    ORDER BY is_default DESC, version DESC
                    LIMIT 1
                """, (content_type, language))
                
                row = await cursor.fetchone()
                if row:
                    return row[0]
                    
                # Fallback to English if available
                if language != 'en':
                    cursor = await db.execute("""
                        SELECT template FROM prompt_templates 
                        WHERE content_type = ? AND language = 'en' AND is_active = 1
                        ORDER BY is_default DESC, version DESC
                        LIMIT 1
                    """, (content_type,))
                    
                    row = await cursor.fetchone()
                    if row:
                        return row[0]
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get prompt template: {e}")
            return None

    # ========================================
    # USER MANAGEMENT METHODS
    # ========================================
    
    async def get_or_create_user(self, telegram_id: int, **user_data) -> Dict[str, Any]:
        """Get existing user or create new one."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                # Try to get existing user
                cursor = await db.execute("""
                    SELECT * FROM users WHERE telegram_id = ?
                """, (telegram_id,))
                
                user = await cursor.fetchone()
                if user:
                    return dict(user)
                
                # Create new user
                await db.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_name, language_code)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    telegram_id,
                    user_data.get('username'),
                    user_data.get('first_name'),
                    user_data.get('last_name'),
                    user_data.get('language_code', 'fr')
                ))
                await db.commit()
                
                # Return the created user
                cursor = await db.execute("""
                    SELECT * FROM users WHERE telegram_id = ?
                """, (telegram_id,))
                
                user = await cursor.fetchone()
                return dict(user) if user else {}
                
        except Exception as e:
            logger.error(f"Failed to get/create user: {e}")
            raise

    async def check_user_limits(self, user_id: int) -> Dict[str, Any]:
        """Check user's daily limits and subscription status."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                # Get user info and today's usage
                cursor = await db.execute("""
                    SELECT 
                        u.subscription_type,
                        u.subscription_expires_at,
                        COALESCE(us.requests_count, 0) as today_requests,
                        sp.daily_requests_limit
                    FROM users u
                    LEFT JOIN usage_stats us ON u.id = us.user_id AND us.date = DATE('now')
                    LEFT JOIN subscription_plans sp ON sp.name_key = 'plan_' || u.subscription_type
                    WHERE u.id = ?
                """, (user_id,))
                
                row = await cursor.fetchone()
                if not row:
                    return {'allowed': False, 'reason': 'User not found'}
                
                data = dict(row)
                
                # Check subscription expiry
                if data['subscription_expires_at']:
                    expires = datetime.fromisoformat(data['subscription_expires_at'])
                    if expires < datetime.now():
                        return {'allowed': False, 'reason': 'Subscription expired'}
                
                # Check daily limits
                daily_limit = data['daily_requests_limit'] or 5  # Default free limit
                today_used = data['today_requests'] or 0
                
                if today_used >= daily_limit:
                    return {'allowed': False, 'reason': 'Daily limit reached'}
                
                return {
                    'allowed': True,
                    'requests_remaining': daily_limit - today_used,
                    'subscription_type': data['subscription_type']
                }
                
        except Exception as e:
            logger.error(f"Failed to check user limits: {e}")
            return {'allowed': False, 'reason': 'Database error'}

    async def record_usage(self, user_id: int, tokens_used: int = 0):
        """Record user's API usage for today."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO usage_stats (user_id, date, requests_count, tokens_used)
                    VALUES (?, DATE('now'), 1, ?)
                    ON CONFLICT(user_id, date) DO UPDATE SET
                        requests_count = requests_count + 1,
                        tokens_used = tokens_used + ?
                """, (user_id, tokens_used, tokens_used))
                
                # Also update user's total requests
                await db.execute("""
                    UPDATE users 
                    SET total_requests = total_requests + 1 
                    WHERE id = ?
                """, (user_id,))
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to record usage: {e}")

    # ========================================
    # ANALYTICS METHODS
    # ========================================
    
    async def log_event(self, event_type: str, user_id: Optional[int] = None, data: Optional[Dict] = None):
        """Log analytics event."""
        try:
            import json
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO bot_analytics (event_type, user_id, data)
                    VALUES (?, ?, ?)
                """, (event_type, user_id, json.dumps(data) if data else None))
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    async def log_error(
        self, 
        error_type: str, 
        error_message: str, 
        user_id: Optional[int] = None,
        stack_trace: Optional[str] = None,
        url: Optional[str] = None
    ):
        """Log error to database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO error_logs (user_id, error_type, error_message, stack_trace, url)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, error_type, error_message, stack_trace, url))
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to log error: {e}")

    # ========================================
    # UTILITY METHODS
    # ========================================
    
    async def get_translation(self, key: str, language: str = 'fr') -> Optional[str]:
        """Get translation for a key in specified language."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT value FROM translations 
                    WHERE key = ? AND language = ?
                """, (key, language))
                
                row = await cursor.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Failed to get translation: {e}")
            return None

    async def health_check(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                user_count = await cursor.fetchone()
                
                cursor = await db.execute("SELECT COUNT(*) FROM summaries_cache")
                cache_count = await cursor.fetchone()
                
                return {
                    'status': 'healthy',
                    'users_count': user_count[0] if user_count else 0,
                    'cached_summaries': cache_count[0] if cache_count else 0,
                    'db_size_mb': round(self.db_path.stat().st_size / (1024*1024), 2) if self.db_path.exists() else 0
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    async def close(self):
        """Close database connections."""
        # Connection is created per operation, nothing to close
        pass

# Global instance
_db_manager = None

def get_database_manager(db_path: str = "database/sambot.db") -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager