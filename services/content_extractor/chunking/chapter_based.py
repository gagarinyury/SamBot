"""
Chapter-based chunking strategy.
Splits content based on YouTube video chapters.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a content chunk."""
    chunk_index: int
    chunk_text: str
    start_timestamp: int
    end_timestamp: int
    chunk_length: int
    chunk_tokens: Optional[int] = None
    chapter_title: Optional[str] = None


class ChapterBasedChunker:
    """
    Chunks content based on video chapters.
    Uses chapters from video metadata for semantic boundaries.
    """

    def __init__(self, max_chunk_size: int = 1000):
        """
        Initialize chapter-based chunker.

        Args:
            max_chunk_size: Maximum tokens per chunk
        """
        self.max_chunk_size = max_chunk_size

    def should_use_chapters(
        self,
        chapters: List[Dict],
        video_duration: int
    ) -> bool:
        """
        Determine if chapters should be used for chunking.

        Args:
            chapters: List of chapter dicts from video metadata
            video_duration: Video duration in seconds

        Returns:
            True if chapters are suitable for chunking
        """
        if not chapters or len(chapters) < 2:
            logger.info("Not enough chapters (<2)")
            return False

        # Only use chapters for videos longer than 10 minutes
        if video_duration < 600:
            logger.info(f"Video too short ({video_duration}s < 600s)")
            return False

        # Check if chapters cover most of the video (at least 50%)
        last_chapter_end = chapters[-1].get('end_time', video_duration)
        coverage = last_chapter_end / video_duration if video_duration > 0 else 0

        if coverage < 0.5:
            logger.info(f"Chapters don't cover enough of video ({coverage*100:.1f}% < 50%)")
            return False

        logger.info(f"Chapters suitable: {len(chapters)} chapters covering {coverage*100:.1f}% of video")
        return True

    def chunk_by_chapters(
        self,
        content: str,
        transcript_segments: List[Dict],
        chapters: List[Dict],
        video_duration: int
    ) -> List[Chunk]:
        """
        Chunk content based on chapters.

        Args:
            content: Full transcript text
            transcript_segments: List of segments with timestamps
            chapters: List of chapter dicts
            video_duration: Video duration in seconds

        Returns:
            List of Chunk objects
        """
        chunks = []

        for idx, chapter in enumerate(chapters):
            start_time = chapter.get('start_time', 0)
            end_time = chapter.get('end_time')

            # Last chapter ends at video end
            if end_time is None:
                end_time = video_duration

            # Extract segments for this chapter
            chapter_segments = [
                seg for seg in transcript_segments
                if start_time <= seg.get('start', 0) < end_time
            ]

            if not chapter_segments:
                continue

            # Combine segment texts
            chapter_text = ' '.join([seg.get('text', '') for seg in chapter_segments])

            chunk = Chunk(
                chunk_index=idx,
                chunk_text=chapter_text,
                start_timestamp=start_time,
                end_timestamp=end_time,
                chunk_length=len(chapter_text),
                chapter_title=chapter.get('title', f"Chapter {idx + 1}")
            )

            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} chapter-based chunks")
        return chunks

    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "chapter_based"