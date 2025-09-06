"""
Text formatting utilities for SamBot.
Handles video info formatting, message formatting, and text truncation.
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from models.video import YouTubeVideoInfo, ExtractionResponse


class VideoFormatter:
    """Formats video information for display."""
    
    @staticmethod
    def format_duration(duration_seconds: int) -> str:
        """
        Format video duration from seconds to MM:SS format.
        
        Args:
            duration_seconds: Duration in seconds
            
        Returns:
            Formatted duration string (e.g., "05:30", "1:25:45")
        """
        if duration_seconds < 0:
            return "00:00"
        
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    @staticmethod
    def format_view_count(view_count: int) -> str:
        """
        Format view count with space separators.
        
        Args:
            view_count: Number of views
            
        Returns:
            Formatted view count (e.g., "1 234 567")
        """
        if view_count < 0:
            return "0"
        
        return f"{view_count:,}".replace(',', ' ')
    
    @staticmethod
    def format_publish_date(publish_date: datetime) -> str:
        """
        Format publish date to DD.MM.YYYY format.
        
        Args:
            publish_date: Video publish date
            
        Returns:
            Formatted date string (e.g., "15.03.2024")
        """
        return publish_date.strftime('%d.%m.%Y')
    
    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to specified length with suffix.
        
        Args:
            text: Text to truncate
            max_length: Maximum length including suffix
            suffix: Suffix to add when truncating
            
        Returns:
            Truncated text with suffix if needed
        """
        if not text or len(text) <= max_length:
            return text
        
        if max_length <= len(suffix):
            return suffix[:max_length]
        
        return text[:max_length - len(suffix)] + suffix
    
    @classmethod
    def format_video_info(
        cls,
        video_info: YouTubeVideoInfo,
        max_title_length: int = 500,
        max_description_length: int = 1000
    ) -> Dict[str, str]:
        """
        Format all video information for display.
        
        Args:
            video_info: Video metadata
            max_title_length: Maximum title length
            max_description_length: Maximum description length
            
        Returns:
            Dictionary with formatted video information
        """
        return {
            'title': cls.truncate_text(video_info.title, max_title_length),
            'channel': video_info.channel,
            'duration': cls.format_duration(video_info.duration),
            'views': cls.format_view_count(video_info.view_count),
            'publish_date': cls.format_publish_date(video_info.publish_date),
            'description': cls.truncate_text(
                video_info.description or "Описание отсутствует", 
                max_description_length
            )
        }


class TranscriptFormatter:
    """Formats transcript segments for display."""
    
    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        Format timestamp to MM:SS format.
        
        Args:
            seconds: Timestamp in seconds
            
        Returns:
            Formatted timestamp (e.g., "[05:30]")
        """
        if seconds < 0:
            seconds = 0
        
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"[{minutes:02d}:{secs:02d}]"
    
    @staticmethod
    def format_segment(segment: Dict, include_timestamp: bool = True) -> str:
        """
        Format single transcript segment.
        
        Args:
            segment: Transcript segment with 'start' and 'text' keys
            include_timestamp: Whether to include timestamp
            
        Returns:
            Formatted segment string
        """
        text = segment.get('text', '').strip()
        if not text:
            return ""
        
        if include_timestamp:
            start_time = segment.get('start', 0)
            timestamp = TranscriptFormatter.format_timestamp(start_time)
            return f"{timestamp} {text}"
        
        return text
    
    @classmethod
    def format_transcript_preview(
        cls,
        segments: List[Dict],
        max_segments: int = 20,
        include_timestamps: bool = True
    ) -> str:
        """
        Format transcript preview with limited segments.
        
        Args:
            segments: List of transcript segments
            max_segments: Maximum number of segments to include
            include_timestamps: Whether to include timestamps
            
        Returns:
            Formatted transcript preview
        """
        if not segments:
            return ""
        
        preview_lines = []
        for segment in segments[:max_segments]:
            formatted = cls.format_segment(segment, include_timestamps)
            if formatted:
                preview_lines.append(formatted)
        
        return '\n'.join(preview_lines)


class MessageFormatter:
    """Formats Telegram messages."""
    
    @staticmethod
    def format_video_message(
        video_info: YouTubeVideoInfo,
        transcript_segments: Optional[List[Dict]] = None,
        max_segments: int = 20
    ) -> str:
        """
        Format complete video information message.
        
        Args:
            video_info: Video metadata
            transcript_segments: Optional transcript segments
            max_segments: Maximum transcript segments to show
            
        Returns:
            Formatted HTML message for Telegram
        """
        formatted = VideoFormatter.format_video_info(video_info)
        
        # Base video information
        message_parts = [
            f"🎥 <b>Название:</b> {formatted['title']}",
            f"👤 <b>Канал:</b> {formatted['channel']}",
            f"📅 <b>Дата:</b> {formatted['publish_date']}",
            f"⏱️ <b>Длительность:</b> {formatted['duration']}",
            f"👁️ <b>Просмотры:</b> {formatted['views']}",
            "",  # Empty line
            "📖 <b>Описание</b>",
            formatted['description']
        ]
        
        # Add transcript preview if available
        if transcript_segments:
            transcript_preview = TranscriptFormatter.format_transcript_preview(
                transcript_segments, 
                max_segments=max_segments
            )
            
            if transcript_preview:
                expandable_content = f"📝 НАЧАЛО ВИДЕО:\n{transcript_preview}"
                expandable_block = f"<blockquote expandable>{expandable_content}</blockquote>"
                message_parts.extend(["", expandable_block])
        
        return '\n'.join(message_parts)
    
    @staticmethod
    def format_error_message(error_type: str, details: str = "") -> str:
        """
        Format error message for display.
        
        Args:
            error_type: Type of error
            details: Additional error details
            
        Returns:
            Formatted error message
        """
        error_messages = {
            "video_not_found": "❌ Видео не найдено или недоступно",
            "no_transcript": "❌ Субтитры для видео недоступны",
            "video_too_long": "❌ Видео слишком длинное для обработки",
            "extraction_failed": "❌ Ошибка при извлечении контента",
            "ai_error": "❌ Ошибка при генерации резюме",
            "invalid_url": "❌ Неверная ссылка на YouTube",
        }
        
        base_message = error_messages.get(error_type, f"❌ Неизвестная ошибка: {error_type}")
        
        if details:
            return f"{base_message}\n\n<i>Детали:</i> {details}"
        
        return base_message
    
    @staticmethod
    def format_progress_message(step: str, total_steps: int = 3, current_step: int = 1) -> str:
        """
        Format progress message.
        
        Args:
            step: Current step description
            total_steps: Total number of steps
            current_step: Current step number
            
        Returns:
            Formatted progress message
        """
        progress_bar = "█" * current_step + "░" * (total_steps - current_step)
        return f"⏳ {step}...\n\n[{progress_bar}] {current_step}/{total_steps}"
    
    @staticmethod
    def escape_html(text: str) -> str:
        """
        Escape HTML special characters for Telegram.
        
        Args:
            text: Text to escape
            
        Returns:
            HTML-escaped text
        """
        if not text:
            return ""
        
        replacements = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        }
        
        for char, escaped in replacements.items():
            text = text.replace(char, escaped)
        
        return text