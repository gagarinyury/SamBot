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
        
        # Clean description from links
        clean_description = clean_video_description(video_info.description or "")
        
        # Base video information
        message_parts = [
            f"🎥 <b>Название:</b> {formatted['title']}",
            f"👤 <b>Канал:</b> {formatted['channel']}",
            f"📅 <b>Дата:</b> {formatted['publish_date']}",
            f"⏱️ <b>Длительность:</b> {formatted['duration']}",
            f"👁️ <b>Просмотры:</b> {formatted['views']}",
            "",  # Empty line
            "📖 <b>Описание</b>",
            clean_description
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


def clean_video_description(description: str) -> str:
    """
    Clean video description from links and unwanted content.
    
    Args:
        description: Raw video description
        
    Returns:
        Cleaned description without links
    """
    if not description:
        return "Описание отсутствует"
    
    import re
    import logging
    logger = logging.getLogger(__name__)
    
    # Логируем исходное описание
    logger.info(f"🔍 ИСХОДНОЕ ОПИСАНИЕ (длина {len(description)}): {repr(description[:500])}")
    original_description = description
    
    # Remove URLs (http, https, www, domain.com patterns)
    description = re.sub(r'https?://[^\s]+', '', description)
    description = re.sub(r'www\.[^\s]+', '', description)
    description = re.sub(r'\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*', '', description)
    
    # Remove common promotional text patterns - улучшенные паттерны
    promotional_patterns = [
        r'Download\s+"[^"]*":\s*',  # Download "The Last Drop": 
        r'Download.*?:\s*',
        r'Get\s+.*?:\s*',
        r'Visit.*?:\s*',
        r'Check out.*?:\s*',
        r'utm_source=[^\s&]*',
        r'utm_campaign=[^\s&]*', 
        r'utm_content=[^\s&]*',
        r'utm_term=[^\s&]*',
        r'utm_medium=[^\s&]*',
        r'\?utm_[^\s]*',  # Убираем весь UTM блок
        r'&utm_[^\s]*',
        # Специфичные паттерны для Steam и игр
        r'store\.steampowered\.com[^\s]*',
        r'app/\d+[^\s]*',
    ]
    
    for pattern in promotional_patterns:
        description = re.sub(pattern, '', description, flags=re.IGNORECASE)
    
    # Убираем остатки после ссылок (например "EnglishThe mad honey")
    # Ищем слипшиеся слова с большими буквами посередине
    description = re.sub(r'([a-z])([A-Z][a-z])', r'\1 \2', description)
    
    # Убираем остатки параметров и символов
    description = re.sub(r'[?&=]+', ' ', description)
    
    # Clean up extra whitespace and punctuation
    description = re.sub(r'\s+', ' ', description)
    description = re.sub(r'^\s*[:.,-]+\s*', '', description)  # Убираем знаки в начале
    description = description.strip()
    
    # Логируем результат очистки
    logger.info(f"✅ ОЧИЩЕННОЕ ОПИСАНИЕ (длина {len(description)}): {repr(description[:500])}")
    logger.info(f"📊 УДАЛЕНО СИМВОЛОВ: {len(original_description) - len(description)}")
    
    # If description is too short after cleaning, use fallback
    if len(description) < 10:
        logger.warning(f"⚠️ ОПИСАНИЕ СЛИШКОМ КОРОТКОЕ после очистки: {repr(description)}")
        return "Описание недоступно"
    
    return description


class SummaryFormatter:
    """Formats AI summaries with beautiful Telegram HTML styling."""
    
    @staticmethod
    def format_ai_summary(
        summary_content: str,
        video_title: str = "",
        channel_name: str = "",
        video_duration: str = "",
        processing_info: Dict = None
    ) -> str:
        """
        Format AI summary with beautiful HTML styling for Telegram.
        
        Args:
            summary_content: Raw AI summary content
            video_title: Video title for header
            channel_name: Channel name for meta info
            video_duration: Video duration for meta info
            processing_info: Dict with processing metadata
            
        Returns:
            Beautifully formatted HTML summary
        """
        processing_info = processing_info or {}
        
        # Extract video type from title for smart emoji selection
        title_lower = video_title.lower()
        
        # Smart topic emoji selection
        topic_emoji = "🎥"
        if any(word in title_lower for word in ["алкоголизм", "алкоголь", "зависимость"]):
            topic_emoji = "🍷"
        elif any(word in title_lower for word in ["психология", "психолог", "терапия"]):
            topic_emoji = "🧠"
        elif any(word in title_lower for word in ["бизнес", "деньги", "работа"]):
            topic_emoji = "💼"
        elif any(word in title_lower for word in ["здоровье", "медицина", "врач", "доктор"]):
            topic_emoji = "⚕️"
        elif any(word in title_lower for word in ["технологии", "программирование", "ИТ"]):
            topic_emoji = "💻"
        
        # Create smart title (truncate if too long)
        display_title = video_title
        if len(display_title) > 60:
            display_title = display_title[:57] + "..."
        
        # Build header
        parts = [
            f"🤖 <b>ИИ Резюме: {display_title}</b>"
        ]
        
        # Add meta info if available
        meta_parts = []
        if channel_name:
            meta_parts.append(f"👤 {channel_name}")
        if video_duration:
            meta_parts.append(f"⏱️ {video_duration}")
        meta_parts.append("📊 Анализ контента")
        
        if meta_parts:
            parts.append(f"{topic_emoji} <i>{' | '.join(meta_parts)}</i>")
        
        parts.append("")  # Empty line
        
        # Parse summary content and format it
        formatted_content = SummaryFormatter._parse_and_format_content(summary_content)
        parts.extend(formatted_content)
        
        # Add footer with processing info
        footer_parts = []
        if processing_info.get("processing_time"):
            time_str = f"{processing_info['processing_time']:.1f}с"
            footer_parts.append(f"⏱️ {time_str}")
        
        if processing_info.get("tokens_used"):
            footer_parts.append(f"🔤 {processing_info['tokens_used']} токенов")
        
        if processing_info.get("cache_hit"):
            footer_parts.append("💾 Из кэша")
        
        footer_parts.append("🔗 YouTube → ИИ")
        
        if footer_parts:
            parts.extend(["", f"<i>{' | '.join(footer_parts)}</i>"])
        
        return "\n".join(parts)
    
    @staticmethod
    def _parse_and_format_content(content: str) -> List[str]:
        """
        Parse AI summary content and format it with proper HTML styling.
        
        Args:
            content: Raw AI summary content
            
        Returns:
            List of formatted content lines
        """
        lines = content.strip().split('\n')
        formatted_lines = []
        current_section = []
        expandable_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Main summary (first substantial paragraph)
            if not formatted_lines and len(line) > 50:
                formatted_lines.append(f"🔥 <b>ГЛАВНОЕ:</b> {line}")
                formatted_lines.append("")
                continue
            
            # Section headers (lines ending with ':' or containing section keywords)
            if (line.endswith(':') or 
                any(keyword in line.lower() for keyword in [
                    'ключевые', 'основные', 'признаки', 'симптомы', 'причины',
                    'выводы', 'рекомендации', 'советы', 'заключение'
                ])):
                
                # Process previous section if exists
                if current_section:
                    expandable_content.extend(current_section)
                    current_section = []
                
                # Format section header
                if 'признак' in line.lower() or 'симптом' in line.lower():
                    formatted_lines.append("📋 <b>ПРИЗНАКИ ПРОБЛЕМЫ:</b>")
                elif 'вывод' in line.lower() or 'заключение' in line.lower():
                    formatted_lines.append("💡 <b>ВЫВОДЫ:</b>")
                else:
                    formatted_lines.append(f"📌 <b>{line.upper()}</b>")
                
                continue
            
            # List items (lines starting with bullet points, numbers, or dashes)
            if line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
                # Clean up the line and add warning emoji for important items
                clean_line = line.lstrip('•-* 123456789.')
                if any(word in clean_line.lower() for word in [
                    'утрата', 'потеря', 'контроль', 'зависимость', 'проблема',
                    'оправдание', 'отрицание', 'ежедневно', 'регулярно'
                ]):
                    formatted_lines.append(f"⚠️ <u>{SummaryFormatter._extract_key_term(clean_line)}:</u> {clean_line}")
                else:
                    formatted_lines.append(f"• {clean_line}")
                continue
            
            # Long detailed content goes to expandable section
            if len(line) > 100:
                current_section.append(f"<b>{SummaryFormatter._make_section_title(line)}:</b>")
                current_section.append(line)
                current_section.append("")
                continue
            
            # Regular content
            if len(line) > 30:
                formatted_lines.append(line)
        
        # Add expandable section if there's detailed content
        if expandable_content or current_section:
            formatted_lines.append("")
            
            all_expandable = []
            all_expandable.extend(expandable_content)
            all_expandable.extend(current_section)
            
            expandable_text = "\n".join(all_expandable).strip()
            if expandable_text:
                formatted_lines.append(f"<blockquote expandable>📊 <b>ДЕТАЛЬНЫЙ АНАЛИЗ</b>\n\n{expandable_text}</blockquote>")
        
        return formatted_lines
    
    @staticmethod
    def _extract_key_term(text: str) -> str:
        """Extract key term from beginning of text for highlighting."""
        words = text.split()
        if len(words) >= 2:
            return " ".join(words[:2])
        return words[0] if words else ""
    
    @staticmethod
    def _make_section_title(text: str) -> str:
        """Create a section title from long text."""
        # Common patterns for section titles
        if 'определение' in text.lower():
            return "Определение"
        elif 'признак' in text.lower():
            return "Признаки"
        elif 'причин' in text.lower():
            return "Причины"
        elif 'рекомендац' in text.lower():
            return "Рекомендации"
        else:
            # Use first few words
            words = text.split()
            return " ".join(words[:3])
    
    @staticmethod
    def create_quick_summary_format(main_point: str, key_points: List[str]) -> str:
        """
        Create a quick summary format for brief summaries.
        
        Args:
            main_point: Main conclusion
            key_points: List of key points
            
        Returns:
            Formatted quick summary
        """
        parts = [
            "🤖 <b>Быстрое резюме</b>",
            "",
            f"🔥 <b>СУТЬ:</b> {main_point}",
            ""
        ]
        
        if key_points:
            parts.append("📋 <b>КЛЮЧЕВЫЕ МОМЕНТЫ:</b>")
            for point in key_points[:4]:  # Max 4 points for quick summary
                parts.append(f"• {point}")
        
        return "\n".join(parts)