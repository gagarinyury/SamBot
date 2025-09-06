"""
YouTube service for video extraction and processing.
Clean separation of YouTube-specific business logic from bot handlers.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from models.video import (
    YouTubeVideoInfo, 
    ExtractionRequest, 
    ExtractionResponse, 
    ExtractionStatus
)
from models.user import UserSettings
from utils.formatters import VideoFormatter, TranscriptFormatter, MessageFormatter
from utils.config import get_config, Constants
from extractors.youtube import extract_youtube_content, YouTubeVideoInfo as ExtractorVideoInfo

logger = logging.getLogger(__name__)


class YouTubeService:
    """Service for YouTube video operations."""
    
    def __init__(self):
        """Initialize YouTube service with configuration."""
        self.config = get_config()
        self.formatter = VideoFormatter()
        self.transcript_formatter = TranscriptFormatter()
        self.message_formatter = MessageFormatter()
    
    async def extract_video_info(
        self, 
        url: str, 
        user_id: Optional[int] = None,
        user_settings: Optional[UserSettings] = None
    ) -> ExtractionResponse:
        """
        Extract video information and transcript from YouTube URL.
        
        Args:
            url: YouTube video URL
            user_id: Optional user ID for logging/tracking
            user_settings: Optional user preferences
            
        Returns:
            ExtractionResponse with video data or error
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting video extraction for URL: {url}, user: {user_id}")
            
            # Validate URL format
            if not self._is_valid_youtube_url(url):
                return ExtractionResponse(
                    status=ExtractionStatus.ERROR,
                    content="",
                    error_message="Invalid YouTube URL format"
                )
            
            # Extract content using existing extractor
            extraction_result = await extract_youtube_content(url)
            
            if not extraction_result:
                return ExtractionResponse(
                    status=ExtractionStatus.ERROR,
                    content="",
                    error_message="Failed to extract video content"
                )
            
            # Check if extraction was successful
            if not extraction_result.content:
                error_status = self._map_extraction_error(extraction_result.error_message)
                return ExtractionResponse(
                    status=error_status,
                    content="",
                    error_message=extraction_result.error_message,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )
            
            # Convert extractor result to service response
            processing_time = (datetime.now() - start_time).total_seconds()
            
            response = ExtractionResponse(
                status=ExtractionStatus.SUCCESS,
                content=extraction_result.content,
                video_info=extraction_result.video_info,
                transcript_info=extraction_result.transcript_info,
                transcript_segments=extraction_result.transcript_segments,
                processing_time=processing_time,
                detected_language=extraction_result.detected_language
            )
            
            logger.info(
                f"Successfully extracted video: {extraction_result.video_info.video_id}, "
                f"duration: {extraction_result.video_info.duration}s, "
                f"processing time: {processing_time:.2f}s"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error extracting video {url}: {str(e)}", exc_info=True)
            return ExtractionResponse(
                status=ExtractionStatus.ERROR,
                content="",
                error_message=f"Unexpected error: {str(e)}",
                processing_time=(datetime.now() - start_time).total_seconds()
            )
    
    def format_video_message(
        self, 
        extraction_result: ExtractionResponse,
        user_settings: Optional[UserSettings] = None
    ) -> str:
        """
        Format video information as Telegram message.
        
        Args:
            extraction_result: Extraction result with video data
            user_settings: Optional user preferences
            
        Returns:
            Formatted HTML message for Telegram
        """
        if extraction_result.status != ExtractionStatus.SUCCESS or not extraction_result.video_info:
            logger.warning(f"⚠️ ОШИБКА ИЗВЛЕЧЕНИЯ: {extraction_result.status.value} - {extraction_result.error_message}")
            return self.message_formatter.format_error_message(
                extraction_result.status.value,
                extraction_result.error_message
            )
        
        logger.info(f"🎬 ФОРМАТИРОВАНИЕ ВИДЕО: {extraction_result.video_info.title[:50]}...")
        logger.info(f"📄 ИСХОДНОЕ ОПИСАНИЕ: {repr((extraction_result.video_info.description or '')[:200])}")
        
        return self.message_formatter.format_video_message(
            extraction_result.video_info,
            extraction_result.transcript_segments,
            max_segments=Constants.TRANSCRIPT_PREVIEW_SEGMENTS
        )
    
    def create_expandable_transcript(
        self, 
        video_info: YouTubeVideoInfo,
        transcript_segments: Optional[List[Dict]] = None
    ) -> str:
        """
        Create expandable transcript block for Telegram.
        
        Args:
            video_info: Video metadata
            transcript_segments: Optional transcript segments
            
        Returns:
            HTML expandable block or empty string
        """
        if not transcript_segments:
            return ""
        
        # Format transcript preview
        transcript_preview = self.transcript_formatter.format_transcript_preview(
            transcript_segments,
            max_segments=Constants.TRANSCRIPT_PREVIEW_SEGMENTS,
            include_timestamps=True
        )
        
        if not transcript_preview:
            return ""
        
        # Create expandable content
        original_description = video_info.description or ""
        
        if original_description:
            full_expandable = f"{original_description}\n\n📝 НАЧАЛО ВИДЕО:\n{transcript_preview}"
        else:
            full_expandable = f"📝 НАЧАЛО ВИДЕО:\n{transcript_preview}"
        
        return f"<blockquote expandable>{full_expandable}</blockquote>"
    
    def get_video_summary_info(self, extraction_result: ExtractionResponse) -> Dict:
        """
        Get formatted video information for summary generation.
        
        Args:
            extraction_result: Extraction result
            
        Returns:
            Dictionary with video info for display
        """
        if not extraction_result.video_info:
            return {}
        
        return self.formatter.format_video_info(
            extraction_result.video_info,
            max_title_length=Constants.TITLE_TRUNCATE_LENGTH,
            max_description_length=Constants.DESCRIPTION_TRUNCATE_LENGTH
        )
    
    def validate_video_duration(self, video_info: YouTubeVideoInfo) -> bool:
        """
        Check if video duration is within acceptable limits.
        
        Args:
            video_info: Video metadata
            
        Returns:
            True if duration is acceptable
        """
        if video_info.duration < Constants.MIN_VIDEO_DURATION:
            return False
        
        if video_info.duration > self.config.max_video_duration:
            return False
        
        return True
    
    def _is_valid_youtube_url(self, url: str) -> bool:
        """
        Validate YouTube URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL appears to be a valid YouTube URL
        """
        if not url:
            return False
        
        # Basic YouTube URL patterns
        youtube_patterns = [
            'youtube.com/watch?v=',
            'youtu.be/',
            'm.youtube.com/watch?v=',
            'www.youtube.com/watch?v='
        ]
        
        return any(pattern in url for pattern in youtube_patterns)
    
    def _map_extraction_error(self, error_message: str) -> ExtractionStatus:
        """
        Map extractor error messages to service status codes.
        
        Args:
            error_message: Error message from extractor
            
        Returns:
            Appropriate ExtractionStatus
        """
        if not error_message:
            return ExtractionStatus.ERROR
        
        error_lower = error_message.lower()
        
        if 'not found' in error_lower or 'unavailable' in error_lower:
            return ExtractionStatus.VIDEO_NOT_FOUND
        elif 'transcript' in error_lower or 'subtitle' in error_lower:
            return ExtractionStatus.NO_TRANSCRIPT
        elif 'too long' in error_lower or 'duration' in error_lower:
            return ExtractionStatus.VIDEO_TOO_LONG
        else:
            return ExtractionStatus.ERROR
    
    def get_progress_message(self, step: str, current: int = 1, total: int = 3) -> str:
        """
        Get formatted progress message for extraction process.
        
        Args:
            step: Current step description
            current: Current step number
            total: Total steps
            
        Returns:
            Formatted progress message
        """
        return self.message_formatter.format_progress_message(step, total, current)
    
    def should_use_fallback_message(self, message_length: int) -> bool:
        """
        Check if message is too long and needs fallback formatting.
        
        Args:
            message_length: Length of formatted message
            
        Returns:
            True if fallback needed
        """
        return message_length > Constants.TELEGRAM_MESSAGE_LIMIT
    
    def create_fallback_message(
        self, 
        video_info: YouTubeVideoInfo,
        max_description_length: int = 500
    ) -> str:
        """
        Create fallback message for cases where main message is too long.
        
        Args:
            video_info: Video metadata
            max_description_length: Maximum description length
            
        Returns:
            Shortened formatted message
        """
        formatted = self.formatter.format_video_info(
            video_info,
            max_description_length=max_description_length
        )
        
        return (
            f"🎥 <b>Название:</b> {formatted['title']}\n"
            f"👤 <b>Канал:</b> {formatted['channel']}\n"
            f"📅 <b>Дата:</b> {formatted['publish_date']}\n"
            f"⏱️ <b>Длительность:</b> {formatted['duration']}\n"
            f"👁️ <b>Просмотры:</b> {formatted['views']}\n\n"
            f"📖 <b>Описание:</b> {formatted['description']}"
        )
    
    async def get_video_metadata_only(self, url: str) -> Optional[YouTubeVideoInfo]:
        """
        Extract only video metadata without transcript (faster).
        
        Args:
            url: YouTube video URL
            
        Returns:
            Video metadata or None if failed
        """
        try:
            extraction_result = await self.extract_video_info(url)
            
            if extraction_result.status == ExtractionStatus.SUCCESS:
                return extraction_result.video_info
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting video metadata for {url}: {str(e)}")
            return None