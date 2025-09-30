"""
YouTube Content Extractor - yt-dlp implementation
Extracts transcripts and metadata from YouTube videos using yt-dlp.
More reliable than youtube-transcript-api for bypassing IP blocks.
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

import validators
import yt_dlp
from langdetect import detect, DetectorFactory

from .chapters import extract_video_chapters
from utils.rate_limiter import youtube_rate_limiter

logger = logging.getLogger(__name__)
DetectorFactory.seed = 0


class ExtractionStatus(Enum):
    """Status of content extraction."""
    SUCCESS = "success"
    NO_TRANSCRIPT = "no_transcript"
    VIDEO_UNAVAILABLE = "video_unavailable"
    INVALID_URL = "invalid_url"
    ERROR = "error"


@dataclass
class YouTubeVideoInfo:
    """YouTube video metadata."""
    video_id: str
    title: str
    channel: str
    duration: int  # seconds
    description: str
    view_count: int = 0
    publish_date: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    chapters: Optional[Dict] = None  # Chapter information


@dataclass
class TranscriptInfo:
    """Information about available transcript."""
    language: str
    language_code: str
    is_generated: bool


@dataclass
class ExtractionResponse:
    """Response from YouTube content extraction."""
    status: ExtractionStatus
    content: str
    video_info: Optional[YouTubeVideoInfo] = None
    transcript_info: Optional[TranscriptInfo] = None
    transcript_segments: Optional[List[Dict]] = None
    processing_time: float = 0.0
    error_message: str = ""
    detected_language: Optional[str] = None


class YouTubeExtractor:
    """YouTube content extractor with transcript and metadata using yt-dlp."""

    def __init__(self):
        self.youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        ]

        # Configure yt-dlp options with anti-blocking measures
        self.ydl_opts = {
            # Basic options
            'quiet': False,  # Enable output for debugging
            'no_warnings': False,
            'verbose': True,  # Enable verbose mode to see plugin messages
            'skip_download': True,
            'socket_timeout': 30,

            # Subtitles
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'ru', 'fr'],

            # Anti-blocking: Sleep intervals (secondary protection)
            # Primary rate limiting is handled by rate_limiter.py (1 video/minute)
            'sleep_interval': 2,           # 2 seconds between API calls within one video
            'max_sleep_interval': 5,       # Random up to 5 seconds
            'sleep_interval_subtitles': 1, # 1 second between subtitle requests

            # Anti-blocking: Source address (bind to external IP, not Docker internal)
            'source_address': '0.0.0.0',   # Let system choose best route

            # Anti-blocking: Cookies from file (bypass bot detection)
            # Note: cookiesfrombrowser doesn't work in Docker (can't access host browser)
            # Use cookiefile instead - see LINUX_DEPLOYMENT_COOKIES.md
            # 'cookiesfrombrowser': (os.getenv('COOKIES_BROWSER', 'chrome'),),
            'cookiefile': os.getenv('COOKIES_FILE') if os.getenv('COOKIES_FILE') else None,

            # Anti-blocking: User-Agent (look like a browser)
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
            },

            # Retry logic
            'retries': 2,
            'fragment_retries': 2,
            'extractor_retries': 2,
        }

        # PO Token Provider DISABLED - it causes MORE blocking instead of helping
        # YouTube blocks requests WITH POT tokens more aggressively than without
        # Simple requests work better for most videos
        logger.info("YouTube extractor initialized WITHOUT POT provider (works better)")

        logger.info("YouTube extractor (yt-dlp) initialized with anti-blocking measures")

    def validate_youtube_url(self, url: str) -> bool:
        """Validate if URL is a valid YouTube URL."""
        if not url or not isinstance(url, str):
            return False

        if not validators.url(url):
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                if not validators.url(url):
                    return False

        for pattern in self.youtube_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True

        return False

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        for pattern in self.youtube_patterns:
            match = re.match(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _parse_vtt_timestamp(self, timestamp: str) -> float:
        """Parse VTT timestamp (00:00:00.000) to seconds."""
        try:
            parts = timestamp.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                total = float(hours) * 3600 + float(minutes) * 60 + float(seconds)
                return total
            elif len(parts) == 2:
                minutes, seconds = parts
                return float(minutes) * 60 + float(seconds)
            else:
                return float(timestamp)
        except:
            return 0.0

    def _parse_vtt_subtitles(self, vtt_content: str) -> tuple[str, List[Dict]]:
        """Parse VTT subtitle content to extract text and segments."""
        segments = []
        full_text_parts = []

        # Split by double newline to get cue blocks
        blocks = re.split(r'\n\n+', vtt_content)

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 2:
                continue

            # Look for timestamp line (format: 00:00:00.000 --> 00:00:03.000)
            timestamp_line = None
            text_lines = []

            for i, line in enumerate(lines):
                if '-->' in line:
                    timestamp_line = line
                    text_lines = lines[i+1:]
                    break

            if not timestamp_line or not text_lines:
                continue

            # Parse timestamps
            try:
                start_str, end_str = timestamp_line.split('-->')
                start = self._parse_vtt_timestamp(start_str.strip())
                end = self._parse_vtt_timestamp(end_str.strip().split()[0])

                # Clean text (remove tags)
                text = ' '.join(text_lines)
                text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                text = text.strip()

                if text:
                    segments.append({
                        'text': text,
                        'start': start,
                        'duration': end - start
                    })
                    full_text_parts.append(text)
            except:
                continue

        full_text = ' '.join(full_text_parts)
        return full_text, segments

    async def get_video_info_and_transcript(
        self,
        url: str,
        preferred_languages: List[str] = None
    ) -> tuple[Optional[YouTubeVideoInfo], Optional[str], Optional[List[Dict]], Optional[TranscriptInfo]]:
        """Get video info and transcript using yt-dlp."""
        if preferred_languages is None:
            preferred_languages = ['en', 'ru', 'fr']

        try:
            # RATE LIMITING: 1 video per minute (safe for production)
            wait_time = await asyncio.get_event_loop().run_in_executor(
                None, youtube_rate_limiter.wait_if_needed
            )
            if wait_time > 0:
                logger.info(f"Rate limited: waited {wait_time:.1f}s")

            # Run yt-dlp in executor to avoid blocking
            loop = asyncio.get_event_loop()

            def extract_info():
                logger.info(f"yt-dlp options: cookiefile={self.ydl_opts.get('cookiefile')}, quiet={self.ydl_opts.get('quiet')}")
                logger.info(f"yt-dlp extractor_args: {self.ydl_opts.get('extractor_args')}")
                logger.info(f"yt-dlp ALL options keys: {list(self.ydl_opts.keys())}")
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await loop.run_in_executor(None, extract_info)

            if not info:
                return None, None, None, None

            # Extract metadata
            video_id = info.get('id', '')
            title = info.get('title', f'YouTube Video {video_id}')
            channel = info.get('uploader') or info.get('channel', 'Unknown Channel')
            duration = int(info.get('duration', 0))
            description = info.get('description', '')
            view_count = int(info.get('view_count', 0))

            # Parse publish date
            publish_date = None
            upload_date_str = info.get('upload_date')
            if upload_date_str:
                try:
                    publish_date = datetime.strptime(upload_date_str, '%Y%m%d')
                except:
                    pass

            # Extract chapters from description
            chapters_data = None
            if description and duration > 0:
                chapters_result = extract_video_chapters(description, duration)
                if chapters_result.get('has_chapters'):
                    chapters_data = chapters_result

            video_info = YouTubeVideoInfo(
                video_id=video_id,
                title=title,
                channel=channel,
                duration=duration,
                description=description,
                view_count=view_count,
                publish_date=publish_date,
                thumbnail_url=info.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                chapters=chapters_data
            )

            # Try to get subtitles
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})

            transcript_text = None
            transcript_segments = None
            transcript_info = None

            # Try manual subtitles first
            for lang in preferred_languages:
                if lang in subtitles:
                    # Find VTT format (skip HLS m3u8 playlists)
                    for sub in subtitles[lang]:
                        if sub.get('ext') == 'vtt' and sub.get('protocol') != 'm3u8_native':
                            vtt_url = sub.get('url')
                            if vtt_url:
                                try:
                                    # Download VTT content
                                    import aiohttp
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(vtt_url) as resp:
                                            if resp.status == 200:
                                                vtt_content = await resp.text()
                                                transcript_text, transcript_segments = self._parse_vtt_subtitles(vtt_content)

                                                transcript_info = TranscriptInfo(
                                                    language=lang,
                                                    language_code=lang,
                                                    is_generated=False
                                                )
                                                logger.info(f"Found manual transcript: {lang}")
                                                break
                                except Exception as e:
                                    logger.debug(f"Error downloading VTT: {e}")

                        if transcript_text:
                            break

                if transcript_text:
                    break

            # Try automatic captions if no manual transcript
            if not transcript_text:
                for lang in preferred_languages:
                    if lang in automatic_captions:
                        # Find VTT format (skip HLS m3u8 playlists)
                        for sub in automatic_captions[lang]:
                            if sub.get('ext') == 'vtt' and sub.get('protocol') != 'm3u8_native':
                                vtt_url = sub.get('url')
                                if vtt_url:
                                    try:
                                        import aiohttp
                                        async with aiohttp.ClientSession() as session:
                                            async with session.get(vtt_url) as resp:
                                                if resp.status == 200:
                                                    vtt_content = await resp.text()
                                                    transcript_text, transcript_segments = self._parse_vtt_subtitles(vtt_content)

                                                    transcript_info = TranscriptInfo(
                                                        language=lang,
                                                        language_code=lang,
                                                        is_generated=True
                                                    )
                                                    logger.info(f"Found auto-generated transcript: {lang}")
                                                    break
                                    except Exception as e:
                                        logger.debug(f"Error downloading automatic VTT: {e}")

                            if transcript_text:
                                break

                    if transcript_text:
                        break

            return video_info, transcript_text, transcript_segments, transcript_info

        except Exception as e:
            logger.error(f"Error getting video info/transcript: {e}")
            return None, None, None, None

    async def extract(
        self,
        url: str,
        preferred_languages: List[str] = None
    ) -> ExtractionResponse:
        """Extract content from YouTube URL."""
        import time
        start_time = time.time()

        try:
            # Validate URL
            if not self.validate_youtube_url(url):
                return ExtractionResponse(
                    status=ExtractionStatus.INVALID_URL,
                    content="",
                    error_message="Invalid YouTube URL"
                )

            # Extract video ID
            video_id = self.extract_video_id(url)
            if not video_id:
                return ExtractionResponse(
                    status=ExtractionStatus.INVALID_URL,
                    content="",
                    error_message="Could not extract video ID"
                )

            # Get metadata and transcript
            video_info, content, segments, transcript_info = await self.get_video_info_and_transcript(
                url,
                preferred_languages
            )

            if not video_info:
                return ExtractionResponse(
                    status=ExtractionStatus.VIDEO_UNAVAILABLE,
                    content="",
                    error_message="Could not get video metadata"
                )

            if not content:
                return ExtractionResponse(
                    status=ExtractionStatus.NO_TRANSCRIPT,
                    content="",
                    video_info=video_info,
                    error_message="No transcript available"
                )

            # Detect language
            try:
                detected_lang = detect(content[:1000])
            except:
                detected_lang = None

            processing_time = time.time() - start_time

            return ExtractionResponse(
                status=ExtractionStatus.SUCCESS,
                content=content,
                video_info=video_info,
                transcript_info=transcript_info,
                transcript_segments=segments,
                processing_time=processing_time,
                detected_language=detected_lang
            )

        except Exception as e:
            logger.error(f"Extraction error: {e}")
            processing_time = time.time() - start_time
            return ExtractionResponse(
                status=ExtractionStatus.ERROR,
                content="",
                error_message=str(e),
                processing_time=processing_time
            )