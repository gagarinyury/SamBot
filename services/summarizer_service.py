"""
Summarizer service for AI-powered content summarization.
Clean wrapper around DeepSeek summarizer with additional business logic.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

from models.video import YouTubeVideoInfo, ExtractionResponse
from models.user import UserSettings
from utils.config import get_config, Constants
from utils.formatters import MessageFormatter, SummaryFormatter
from summarizers.deepseek import summarize_content, SummaryLength, SummaryResponse

logger = logging.getLogger(__name__)


class SummarizerService:
    """Service for AI content summarization."""
    
    def __init__(self):
        """Initialize summarizer service with configuration."""
        self.config = get_config()
        self.message_formatter = MessageFormatter()
        
        # Language mapping for UI display
        self.languages = {
            "ru": {
                "name": "русский",
                "flag": "🇷🇺",
                "emoji": "🗣️"
            },
            "en": {
                "name": "английский", 
                "flag": "🇺🇸",
                "emoji": "🗣️"
            },
            "fr": {
                "name": "французский",
                "flag": "🇫🇷", 
                "emoji": "🗣️"
            }
        }
        
        # Summary type mapping for UI display
        self.summary_types = {
            "brief": {
                "name": "Краткое",
                "desc": "основные моменты",
                "emoji": "⚡"
            },
            "detailed": {
                "name": "Подробное",
                "desc": "детальный анализ",
                "emoji": "📖"
            }
        }
    
    async def generate_summary(
        self,
        content: str,
        video_info: Optional[YouTubeVideoInfo] = None,
        user_settings: Optional[UserSettings] = None,
        user_id: Optional[int] = None,
        original_url: Optional[str] = None
    ) -> Dict:
        """
        Generate AI summary for video content.
        
        Args:
            content: Video transcript content
            video_info: Optional video metadata
            user_settings: User preferences
            user_id: User ID for tracking
            original_url: Original video URL
            
        Returns:
            Dictionary with summary result and display info
        """
        start_time = datetime.now()
        
        try:
            # Use default settings if not provided
            settings = user_settings or UserSettings(
                user_id=user_id or 0,
                language=self.config.default_language,
                summary_type=self.config.default_summary_type
            )
            
            logger.info(
                f"Generating summary for user {user_id}, "
                f"language: {settings.language}, type: {settings.summary_type}"
            )
            
            # Validate content length
            if len(content) > self.config.max_text_length:
                return {
                    "success": False,
                    "error": f"Content too long ({len(content)} chars, max: {self.config.max_text_length})",
                    "error_type": "content_too_long"
                }
            
            # Get language and summary type info for display
            lang_info = self.languages.get(settings.language, self.languages["ru"])
            summary_info = self.summary_types.get(settings.summary_type, self.summary_types["detailed"])
            
            # Map summary type to enum
            summary_length = (
                SummaryLength.BRIEF 
                if settings.summary_type == "brief" 
                else SummaryLength.DETAILED
            )
            
            # Generate summary using DeepSeek
            summary_response = await summarize_content(
                content=content,
                content_type="youtube",
                target_language=settings.language,
                summary_length=summary_length.value,
                user_id=user_id,
                original_url=original_url
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if not summary_response or not summary_response.summary:
                logger.error(f"Summary generation failed for user {user_id}")
                return {
                    "success": False,
                    "error": "AI summary generation failed",
                    "error_type": "ai_error",
                    "processing_time": processing_time
                }
            
            # Format success response
            result = {
                "success": True,
                "summary": summary_response.summary,
                "processing_time": processing_time,
                "language_info": lang_info,
                "summary_info": summary_info,
                "tokens_used": getattr(summary_response, 'tokens_used', 0),
                "model_used": getattr(summary_response, 'model_used', 'deepseek'),
                "cache_hit": getattr(summary_response, 'cache_hit', False)
            }
            
            # Add video info if available
            if video_info:
                result["video_title"] = video_info.title
                result["video_channel"] = video_info.channel
                result["video_duration"] = video_info.duration
            
            logger.info(
                f"Successfully generated summary for user {user_id}, "
                f"processing time: {processing_time:.2f}s, "
                f"tokens used: {result.get('tokens_used', 0)}"
            )
            
            return result
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error generating summary for user {user_id}: {str(e)}", exc_info=True)
            
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "unexpected_error",
                "processing_time": processing_time
            }
    
    def format_summary_message(
        self,
        summary_result: Dict,
        video_info: Optional[YouTubeVideoInfo] = None
    ) -> str:
        """
        Format summary result as beautiful Telegram message using new formatter.
        
        Args:
            summary_result: Result from generate_summary
            video_info: Optional video metadata
            
        Returns:
            Beautifully formatted HTML message for Telegram
        """
        if not summary_result.get("success"):
            error_type = summary_result.get("error_type", "unknown")
            error_message = summary_result.get("error", "Unknown error")
            
            return self.message_formatter.format_error_message(error_type, error_message)
        
        summary_text = summary_result.get("summary", "")
        processing_time = summary_result.get("processing_time", 0)
        tokens_used = summary_result.get("tokens_used", 0)
        cache_hit = summary_result.get("cache_hit", False)
        
        # Prepare video info
        video_title = ""
        channel_name = ""
        video_duration = ""
        
        if video_info:
            video_title = video_info.title
            channel_name = video_info.channel
            
            # Format duration
            duration_mins = video_info.duration // 60
            duration_secs = video_info.duration % 60
            video_duration = f"{duration_mins}:{duration_secs:02d}"
        
        # Prepare processing info
        processing_info = {
            "processing_time": processing_time,
            "tokens_used": tokens_used,
            "cache_hit": cache_hit
        }
        
        # Use new beautiful formatter
        return SummaryFormatter.format_ai_summary(
            summary_content=summary_text,
            video_title=video_title,
            channel_name=channel_name,
            video_duration=video_duration,
            processing_info=processing_info
        )
    
    def get_progress_message(
        self,
        user_settings: Optional[UserSettings] = None,
        step: str = "Анализирую контент с помощью ИИ..."
    ) -> str:
        """
        Get formatted progress message for summary generation.
        
        Args:
            user_settings: User preferences for display
            step: Current step description
            
        Returns:
            Formatted progress message
        """
        # Use default settings if not provided
        if not user_settings:
            user_settings = UserSettings(
                user_id=0,
                language=self.config.default_language,
                summary_type=self.config.default_summary_type
            )
        
        lang_info = self.languages.get(user_settings.language, self.languages["ru"])
        summary_info = self.summary_types.get(user_settings.summary_type, self.summary_types["detailed"])
        
        return (
            f"🤖 <b>Создаю {summary_info['name'].lower()} резюме...</b>\n\n"
            f"🌐 Язык: {lang_info['emoji']} на {lang_info['flag']}\n"
            f"📋 Тип: {summary_info['emoji']} {summary_info['desc']}\n\n"
            f"⏳ <i>{step}</i>"
        )
    
    def validate_content_length(self, content: str) -> bool:
        """
        Check if content length is acceptable for summarization.
        
        Args:
            content: Content to validate
            
        Returns:
            True if content length is acceptable
        """
        if not content:
            return False
        
        if len(content.strip()) < 100:  # Too short to summarize meaningfully
            return False
        
        if len(content) > self.config.max_text_length:
            return False
        
        return True
    
    def get_supported_languages(self) -> Dict:
        """
        Get list of supported languages for UI.
        
        Returns:
            Dictionary mapping language codes to display info
        """
        return self.languages.copy()
    
    def get_summary_types(self) -> Dict:
        """
        Get list of supported summary types for UI.
        
        Returns:
            Dictionary mapping summary types to display info
        """
        return self.summary_types.copy()
    
    def estimate_processing_time(self, content_length: int) -> int:
        """
        Estimate processing time based on content length.
        
        Args:
            content_length: Length of content in characters
            
        Returns:
            Estimated processing time in seconds
        """
        # Rough estimate: ~1 second per 1000 characters
        base_time = max(3, content_length // 1000)
        return min(base_time, 30)  # Cap at 30 seconds
    
    async def get_summary_statistics(self, user_id: int) -> Dict:
        """
        Get user's summary usage statistics.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            # This would typically query a database
            # For now, return placeholder data
            return {
                "total_summaries": 0,
                "total_tokens": 0,
                "favorite_language": self.config.default_language,
                "favorite_summary_type": self.config.default_summary_type
            }
        except Exception as e:
            logger.error(f"Error getting summary statistics for user {user_id}: {str(e)}")
            return {}
    
    def should_suggest_brief_summary(self, content_length: int) -> bool:
        """
        Check if brief summary should be suggested based on content length.
        
        Args:
            content_length: Length of content
            
        Returns:
            True if brief summary is recommended
        """
        # Suggest brief summary for shorter content
        return content_length < 5000