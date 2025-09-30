"""Pydantic models for Content Extractor service."""

from typing import Optional, Literal
from pydantic import BaseModel, HttpUrl


class ExtractionRequest(BaseModel):
    """Request model for content extraction."""
    url: str
    user_id: Optional[int] = None
    language: Optional[str] = None


class ContentMetadata(BaseModel):
    """Metadata extracted from content."""
    title: str
    channel: Optional[str] = None
    duration: Optional[float] = None  # seconds (can be fractional)
    description: Optional[str] = None
    language: Optional[str] = None
    platform: str


class ExtractionResponse(BaseModel):
    """Response model for successful extraction."""
    status: Literal["success", "cached"]
    content_id: int
    strategy: Literal["transcript", "audio", "whisper"]
    extraction_method: str
    metadata: ContentMetadata
    has_transcript: bool
    has_audio: bool
    transcript_length: Optional[int] = None
    audio_file: Optional[str] = None
    total_chunks: int
    processing_time: float


class ErrorResponse(BaseModel):
    """Response model for errors."""
    status: Literal["error"]
    error: str
    details: Optional[str] = None