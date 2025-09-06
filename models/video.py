"""
Video and extraction data models.
Extracted from extractors/youtube.py for better modularity.
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class TranscriptType(Enum):
    """Types of available transcripts."""
    MANUAL = "manual"
    AUTO_GENERATED = "auto_generated"
    UNAVAILABLE = "unavailable"


class ExtractionStatus(Enum):
    """Status of content extraction."""
    SUCCESS = "success"
    NO_TRANSCRIPT = "no_transcript"
    ERROR = "error"
    VIDEO_NOT_FOUND = "video_not_found"
    VIDEO_UNAVAILABLE = "video_unavailable"
    VIDEO_TOO_LONG = "video_too_long"


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