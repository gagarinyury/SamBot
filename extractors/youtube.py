"""
YouTube Content Extractor
Extracts transcripts and metadata from YouTube videos using youtube-transcript-api and pytube.
"""

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.parse import urlparse, parse_qs

import validators
import aiohttp
from langdetect import detect, DetectorFactory
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, VideoUnavailable
from pytube import YouTube, exceptions as pytube_exceptions

from config import get_config
from database.manager import get_database_manager

# Configure logging
logger = logging.getLogger(__name__)

# Make language detection deterministic
DetectorFactory.seed = 0

class TranscriptType(Enum):
    """Types of available transcripts."""
    MANUAL = "manual"
    AUTO_GENERATED = "auto_generated"
    UNAVAILABLE = "unavailable"

class ExtractionStatus(Enum):
    """Status of content extraction."""
    SUCCESS = "success"
    NO_TRANSCRIPT = "no_transcript"
    VIDEO_UNAVAILABLE = "video_unavailable"
    PRIVATE_VIDEO = "private_video"
    INVALID_URL = "invalid_url"
    LANGUAGE_NOT_AVAILABLE = "language_not_available"
    DURATION_EXCEEDED = "duration_exceeded"
    ERROR = "error"

@dataclass
class YouTubeVideoInfo:
    """YouTube video metadata."""
    video_id: str
    title: str
    channel: str
    duration: int  # seconds
    view_count: int
    publish_date: datetime
    description: str
    language: Optional[str] = None
    thumbnail_url: Optional[str] = None

@dataclass
class TranscriptInfo:
    """Information about available transcript."""
    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool

@dataclass
class ExtractionRequest:
    """Request data for YouTube content extraction."""
    url: str
    preferred_languages: List[str] = None
    allow_auto_generated: bool = True
    user_id: Optional[int] = None
    
    def __post_init__(self):
        if self.preferred_languages is None:
            self.preferred_languages = ['fr', 'en', 'ru']  # France market default

@dataclass
class ExtractionResponse:
    """Response from YouTube content extraction."""
    status: ExtractionStatus
    content: str
    video_info: Optional[YouTubeVideoInfo] = None
    transcript_info: Optional[TranscriptInfo] = None
    transcript_segments: Optional[List[Dict]] = None  # Raw segments with timestamps
    processing_time: float = 0.0
    error_message: str = ""
    detected_language: Optional[str] = None
    used_language: Optional[str] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

class YouTubeExtractorError(Exception):
    """YouTube extractor specific errors."""
    pass

class VideoUnavailableError(YouTubeExtractorError):
    """Video is not available for extraction."""
    pass

class TranscriptUnavailableError(YouTubeExtractorError):
    """No suitable transcript is available."""
    pass

class YouTubeExtractor:
    """
    Advanced YouTube content extractor with multilingual transcript support,
    video metadata extraction, and comprehensive error handling.
    """
    
    def __init__(self, database_manager=None):
        self.config = get_config()
        self.db = database_manager or get_database_manager()
        
        # YouTube-specific configuration
        self.youtube_config = self.config.youtube
        
        # YouTube transcript API client
        self.transcript_api = YouTubeTranscriptApi()
        
        # URL patterns for YouTube
        self.youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]
        
        # Statistics
        self.stats = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'transcript_cache_hits': 0,
            'auto_generated_used': 0,
            'manual_transcripts_used': 0,
        }
        
        logger.info("YouTube extractor initialized")

    def validate_youtube_url(self, url: str) -> bool:
        """
        Validate if URL is a valid YouTube URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid YouTube URL, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
            
        # Basic URL validation
        if not validators.url(url):
            # Try to add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                if not validators.url(url):
                    return False
        
        # Check against YouTube patterns
        for pattern in self.youtube_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
                
        return False

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL.
        
        Args:
            url: YouTube URL
            
        Returns:
            Video ID or None if not found
        """
        for pattern in self.youtube_patterns:
            match = re.match(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    async def get_video_metadata_from_html(self, video_id: str) -> Optional[YouTubeVideoInfo]:
        """
        Get video metadata by parsing HTML page.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video metadata extracted from HTML or None
        """
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
            
            # Parse metadata from HTML
            title = self._extract_from_html(html, r'<title>([^<]+)</title>')
            if title:
                title = title.replace(' - YouTube', '').strip()
            
            # Try different patterns for author
            author = (
                self._extract_from_html(html, r'<link itemprop="name" content="([^"]+)">') or
                self._extract_from_html(html, r'"name":"([^"]+)"', context='"@type":"Person"') or
                self._extract_from_html(html, r'"author":"([^"]+)"') 
            )
            
            # Parse duration from PT format (PT26M58S -> seconds)
            duration_str = self._extract_from_html(html, r'content="(PT[^"]+)"')
            duration = self._parse_duration(duration_str) if duration_str else 0
            
            # Parse view count - get the bigger number (views, not likes)
            view_counts = []
            import re
            for match in re.finditer(r'"userInteractionCount"[^}]*?"(\d+)"', html):
                count = int(match.group(1))
                if count > 1000:  # Views are usually much higher than likes
                    view_counts.append(count)
            view_count = max(view_counts) if view_counts else 0
            
            # Parse upload date
            upload_date_str = self._extract_from_html(html, r'"uploadDate":"([^"]+)"')
            publish_date = self._parse_date(upload_date_str) if upload_date_str else datetime.utcnow()
            
            # Parse description
            description = self._extract_from_html(html, r'<meta name="description" content="([^"]*)"')
            
            return YouTubeVideoInfo(
                video_id=video_id,
                title=title or f"YouTube Video {video_id}",
                channel=author or "Unknown Channel",
                duration=duration,
                view_count=view_count,
                publish_date=publish_date,
                description=description or "",
                thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
            )
            
        except Exception as e:
            logger.error(f"Error parsing HTML metadata for {video_id}: {e}")
            return None
    
    def _extract_from_html(self, html: str, pattern: str, context: str = None) -> Optional[str]:
        """Extract data from HTML using regex."""
        try:
            if context:
                # Find context first, then pattern within that context
                context_match = re.search(re.escape(context) + r'[^}]*', html)
                if context_match:
                    context_text = context_match.group(0)
                    match = re.search(pattern, context_text)
                    return match.group(1) if match else None
            else:
                match = re.search(pattern, html)
                return match.group(1) if match else None
        except Exception:
            return None
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse YouTube duration format PT26M58S to seconds."""
        try:
            if not duration_str.startswith('PT'):
                return 0
                
            duration_str = duration_str[2:]  # Remove 'PT'
            
            # Parse hours, minutes, seconds
            hours = minutes = seconds = 0
            
            if 'H' in duration_str:
                hours_match = re.search(r'(\d+)H', duration_str)
                hours = int(hours_match.group(1)) if hours_match else 0
                
            if 'M' in duration_str:
                minutes_match = re.search(r'(\d+)M', duration_str)
                minutes = int(minutes_match.group(1)) if minutes_match else 0
                
            if 'S' in duration_str:
                seconds_match = re.search(r'(\d+)S', duration_str)
                seconds = int(seconds_match.group(1)) if seconds_match else 0
                
            return hours * 3600 + minutes * 60 + seconds
            
        except Exception:
            return 0
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse YouTube date format to datetime."""
        try:
            # Format: 2025-08-30T23:37:06-07:00
            if 'T' in date_str:
                date_part = date_str.split('T')[0]
                year, month, day = map(int, date_part.split('-'))
                return datetime(year, month, day)
            return datetime.utcnow()
        except Exception:
            return datetime.utcnow()

    async def get_video_info(self, video_id: str) -> Optional[YouTubeVideoInfo]:
        """
        Get video metadata using pytube with HTML parsing fallback.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video metadata or None if unavailable
        """
        # Try pytube first
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            yt = YouTube(url)
            
            # Get publish date (fallback to today if not available)
            publish_date = yt.publish_date if yt.publish_date else datetime.utcnow()
            
            return YouTubeVideoInfo(
                video_id=video_id,
                title=yt.title or f"YouTube Video {video_id}",
                channel=yt.author or "Unknown Channel", 
                duration=yt.length or 0,
                view_count=yt.views or 0,
                publish_date=publish_date,
                description=yt.description or "",
                thumbnail_url=yt.thumbnail_url or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            )
            
        except Exception as e:
            logger.warning(f"Pytube failed for {video_id}: {e}, trying HTML parsing...")
            
            # Fallback to HTML parsing
            html_info = await self.get_video_metadata_from_html(video_id)
            if html_info:
                return html_info
            
            # Final fallback to basic info
            logger.error(f"All metadata extraction methods failed for {video_id}")
            return YouTubeVideoInfo(
                video_id=video_id,
                title=f"YouTube Video {video_id}",
                channel="Unknown Channel",
                duration=0,
                view_count=0,
                publish_date=datetime.utcnow(),
                description="",
                thumbnail_url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            )

    def get_available_transcripts(self, video_id: str) -> List[TranscriptInfo]:
        """
        Get list of available transcripts for video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            List of available transcripts
        """
        try:
            transcript_list = self.transcript_api.list(video_id)
            transcripts = []
            
            for transcript in transcript_list:
                transcripts.append(TranscriptInfo(
                    language=transcript.language,
                    language_code=transcript.language_code,
                    is_generated=transcript.is_generated,
                    is_translatable=hasattr(transcript, 'translation_languages') and len(transcript.translation_languages) > 0
                ))
                
            return transcripts
            
        except (NoTranscriptFound, VideoUnavailable):
            return []
        except Exception as e:
            logger.error(f"Error getting transcript list for {video_id}: {e}")
            return []

    def detect_content_language(self, content: str) -> Optional[str]:
        """
        Detect language of content using langdetect.
        
        Args:
            content: Text content to analyze
            
        Returns:
            Language code or None if detection failed
        """
        try:
            # Only detect if content is substantial
            if len(content.strip()) < 50:
                return None
                
            language = detect(content)
            logger.debug(f"Detected language: {language}")
            return language
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return None

    def select_best_transcript(
        self, 
        transcripts: List[TranscriptInfo], 
        preferred_languages: List[str],
        allow_auto_generated: bool
    ) -> Optional[TranscriptInfo]:
        """
        Select the best available transcript based on preferences.
        
        Args:
            transcripts: Available transcripts
            preferred_languages: Preferred language codes in order
            allow_auto_generated: Whether to accept auto-generated transcripts
            
        Returns:
            Best transcript or None if none suitable
        """
        if not transcripts:
            return None
            
        # Filter by auto-generated preference
        if not allow_auto_generated:
            transcripts = [t for t in transcripts if not t.is_generated]
            
        if not transcripts:
            return None
            
        # Try to find manual transcripts first in preferred languages
        for lang in preferred_languages:
            for transcript in transcripts:
                if (transcript.language_code == lang and not transcript.is_generated):
                    return transcript
                    
        # Then try auto-generated in preferred languages
        if allow_auto_generated:
            for lang in preferred_languages:
                for transcript in transcripts:
                    if (transcript.language_code == lang and transcript.is_generated):
                        return transcript
        
        # Fallback to first manual transcript
        manual_transcripts = [t for t in transcripts if not t.is_generated]
        if manual_transcripts:
            return manual_transcripts[0]
            
        # Final fallback to first auto-generated
        if allow_auto_generated and transcripts:
            return transcripts[0]
            
        return None

    async def extract_transcript(self, video_id: str, transcript_info: TranscriptInfo) -> Tuple[str, List[Dict]]:
        """
        Extract transcript content for video.
        
        Args:
            video_id: YouTube video ID
            transcript_info: Selected transcript information
            
        Returns:
            Tuple of (transcript text content, raw segments with timestamps)
        """
        try:
            # Get transcript list and find the specific transcript
            transcript_list = self.transcript_api.list(video_id)
            transcript = transcript_list.find_transcript([transcript_info.language_code])
            
            # Fetch the transcript data
            transcript_data = transcript.fetch()
            
            # Process transcript entries
            content = []
            segments = []
            
            for entry in transcript_data:
                # Handle both dict and object formats
                if hasattr(entry, 'text'):
                    text = entry.text.strip()
                    start = getattr(entry, 'start', 0)
                    duration = getattr(entry, 'duration', 0)
                elif isinstance(entry, dict):
                    text = entry.get('text', '').strip()
                    start = entry.get('start', 0)
                    duration = entry.get('duration', 0)
                else:
                    # Fallback - convert to string
                    text = str(entry).strip()
                    start = 0
                    duration = 0
                    
                if text:
                    # Clean up text
                    clean_text = re.sub(r'\[.*?\]', '', text)  # Remove [Music], [Applause], etc.
                    clean_text = clean_text.strip()
                    
                    if clean_text:
                        content.append(clean_text)
                        segments.append({
                            'text': clean_text,
                            'start': float(start),
                            'duration': float(duration)
                        })
                    
            full_content = ' '.join(content)
            
            # Normalize whitespace
            full_content = re.sub(r'\s+', ' ', full_content).strip()
            
            return full_content, segments
            
        except Exception as e:
            logger.error(f"Error extracting transcript for {video_id}: {e}")
            raise TranscriptUnavailableError(f"Failed to extract transcript: {e}")

    async def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        """
        Extract content from YouTube video.
        
        Args:
            request: Extraction request
            
        Returns:
            Extraction response with content and metadata
        """
        start_time = time.time()
        self.stats['total_extractions'] += 1
        
        try:
            # Validate URL
            if not self.validate_youtube_url(request.url):
                return ExtractionResponse(
                    status=ExtractionStatus.INVALID_URL,
                    content="",
                    error_message="Invalid YouTube URL",
                    processing_time=time.time() - start_time
                )
            
            # Extract video ID
            video_id = self.extract_video_id(request.url)
            if not video_id:
                return ExtractionResponse(
                    status=ExtractionStatus.INVALID_URL,
                    content="",
                    error_message="Could not extract video ID from URL",
                    processing_time=time.time() - start_time
                )
            
            # Get video metadata
            video_info = await self.get_video_info(video_id)
            if not video_info:
                return ExtractionResponse(
                    status=ExtractionStatus.VIDEO_UNAVAILABLE,
                    content="",
                    error_message="Video is unavailable or private",
                    processing_time=time.time() - start_time
                )
            
            # Check duration limit
            if video_info.duration > self.youtube_config.max_video_duration:
                return ExtractionResponse(
                    status=ExtractionStatus.DURATION_EXCEEDED,
                    content="",
                    video_info=video_info,
                    error_message=f"Video duration {video_info.duration}s exceeds limit {self.youtube_config.max_video_duration}s",
                    processing_time=time.time() - start_time
                )
            
            # Get available transcripts
            transcripts = self.get_available_transcripts(video_id)
            if not transcripts:
                await self.db.log_error(
                    error_type="transcript_unavailable",
                    error_message=f"No transcripts available for video {video_id}",
                    user_id=request.user_id,
                    url=request.url
                )
                return ExtractionResponse(
                    status=ExtractionStatus.NO_TRANSCRIPT,
                    content="",
                    video_info=video_info,
                    error_message="No transcripts available for this video",
                    processing_time=time.time() - start_time
                )
            
            # Select best transcript
            selected_transcript = self.select_best_transcript(
                transcripts, 
                request.preferred_languages,
                request.allow_auto_generated
            )
            
            if not selected_transcript:
                return ExtractionResponse(
                    status=ExtractionStatus.LANGUAGE_NOT_AVAILABLE,
                    content="",
                    video_info=video_info,
                    error_message="No suitable transcript available in preferred languages",
                    processing_time=time.time() - start_time
                )
            
            # Extract transcript content
            content, segments = await self.extract_transcript(video_id, selected_transcript)
            
            if not content or len(content.strip()) < 10:
                return ExtractionResponse(
                    status=ExtractionStatus.NO_TRANSCRIPT,
                    content="",
                    video_info=video_info,
                    transcript_info=selected_transcript,
                    error_message="Transcript content is empty or too short",
                    processing_time=time.time() - start_time
                )
            
            # Detect content language
            detected_language = self.detect_content_language(content)
            
            # Update statistics
            self.stats['successful_extractions'] += 1
            if selected_transcript.is_generated:
                self.stats['auto_generated_used'] += 1
            else:
                self.stats['manual_transcripts_used'] += 1
            
            # Log successful extraction
            await self.db.log_event(
                event_type="youtube_extraction_success",
                user_id=request.user_id,
                data={
                    "video_id": video_id,
                    "transcript_language": selected_transcript.language_code,
                    "transcript_type": "auto" if selected_transcript.is_generated else "manual",
                    "content_length": len(content),
                    "video_duration": video_info.duration
                }
            )
            
            return ExtractionResponse(
                status=ExtractionStatus.SUCCESS,
                content=content,
                video_info=video_info,
                transcript_info=selected_transcript,
                transcript_segments=segments,
                processing_time=time.time() - start_time,
                detected_language=detected_language,
                used_language=selected_transcript.language_code
            )
            
        except TranscriptUnavailableError as e:
            self.stats['failed_extractions'] += 1
            await self.db.log_error(
                error_type="transcript_extraction_failed",
                error_message=str(e),
                user_id=request.user_id,
                url=request.url
            )
            return ExtractionResponse(
                status=ExtractionStatus.NO_TRANSCRIPT,
                content="",
                error_message=str(e),
                processing_time=time.time() - start_time
            )
            
        except VideoUnavailableError as e:
            self.stats['failed_extractions'] += 1
            return ExtractionResponse(
                status=ExtractionStatus.VIDEO_UNAVAILABLE,
                content="",
                error_message=str(e),
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            self.stats['failed_extractions'] += 1
            logger.error(f"Unexpected error in YouTube extraction: {e}")
            await self.db.log_error(
                error_type="youtube_extraction_error",
                error_message=str(e),
                user_id=request.user_id,
                url=request.url
            )
            return ExtractionResponse(
                status=ExtractionStatus.ERROR,
                content="",
                error_message=f"Extraction failed: {e}",
                processing_time=time.time() - start_time
            )

    def get_stats(self) -> Dict:
        """Get extraction statistics."""
        return {
            **self.stats,
            'success_rate': (
                (self.stats['successful_extractions'] / self.stats['total_extractions'] * 100)
                if self.stats['total_extractions'] > 0 else 0
            ),
            'auto_generated_rate': (
                (self.stats['auto_generated_used'] / self.stats['successful_extractions'] * 100)
                if self.stats['successful_extractions'] > 0 else 0
            )
        }

# Global instance
_youtube_extractor = None

def get_youtube_extractor(database_manager=None) -> YouTubeExtractor:
    """Get global YouTube extractor instance."""
    global _youtube_extractor
    if _youtube_extractor is None:
        _youtube_extractor = YouTubeExtractor(database_manager)
    return _youtube_extractor

# Convenience function
async def extract_youtube_content(
    url: str,
    preferred_languages: List[str] = None,
    allow_auto_generated: bool = True,
    user_id: Optional[int] = None
) -> ExtractionResponse:
    """
    Convenience function to extract YouTube content.
    
    Args:
        url: YouTube video URL
        preferred_languages: Preferred transcript languages
        allow_auto_generated: Whether to accept auto-generated transcripts
        user_id: User ID for logging
        
    Returns:
        Extraction response
    """
    extractor = get_youtube_extractor()
    request = ExtractionRequest(
        url=url,
        preferred_languages=preferred_languages,
        allow_auto_generated=allow_auto_generated,
        user_id=user_id
    )
    return await extractor.extract(request)