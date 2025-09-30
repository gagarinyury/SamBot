"""
Fixed-size chunking strategy.
Splits content into fixed-size chunks with overlap.
"""

import logging
import re
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logging.warning("tiktoken not available, using character-based estimation")

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a content chunk."""
    chunk_index: int
    chunk_text: str
    start_timestamp: Optional[int]
    end_timestamp: Optional[int]
    chunk_length: int
    chunk_tokens: Optional[int] = None


class FixedSizeChunker:
    """
    Chunks content into fixed-size pieces with overlap.
    Falls back to character-based if tiktoken not available.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        model: str = "gpt-3.5-turbo"
    ):
        """
        Initialize fixed-size chunker.

        Args:
            chunk_size: Target size in tokens (or characters if tiktoken unavailable)
            overlap: Overlap size in tokens (or characters)
            model: Tokenizer model name
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.encoding_for_model(model)
                self.use_tokens = True
                logger.info(f"Using tiktoken encoding for {model}")
            except:
                self.encoding = None
                self.use_tokens = False
                logger.warning("Failed to load tiktoken, using character-based chunking")
        else:
            self.encoding = None
            self.use_tokens = False

    def count_units(self, text: str) -> int:
        """Count tokens or characters."""
        if self.use_tokens and self.encoding:
            return len(self.encoding.encode(text))
        else:
            return len(text)

    def split_text(self, text: str) -> List[str]:
        """
        Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        # Split by sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_size = self.count_units(sentence)

            if current_size + sentence_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append(chunk_text)

                # Keep overlap
                overlap_sentences = []
                overlap_size = 0
                for s in reversed(current_chunk):
                    s_size = self.count_units(s)
                    if overlap_size + s_size <= self.overlap:
                        overlap_sentences.insert(0, s)
                        overlap_size += s_size
                    else:
                        break

                current_chunk = overlap_sentences
                current_size = overlap_size

            current_chunk.append(sentence)
            current_size += sentence_size

        # Add last chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(chunk_text)

        return chunks

    def estimate_timestamps(
        self,
        chunks: List[str],
        transcript_segments: Optional[List[Dict]],
        video_duration: int
    ) -> List[tuple[int, int]]:
        """
        Estimate start/end timestamps for chunks.

        Args:
            chunks: List of text chunks
            transcript_segments: Original segments with timestamps
            video_duration: Total video duration

        Returns:
            List of (start, end) timestamp tuples
        """
        if not transcript_segments:
            # Distribute evenly
            chunk_duration = video_duration / len(chunks)
            return [
                (int(i * chunk_duration), int((i + 1) * chunk_duration))
                for i in range(len(chunks))
            ]

        # Try to match chunks to segments
        timestamps = []
        segment_idx = 0
        total_segments = len(transcript_segments)

        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_words = set(chunk_text.lower().split())

            # Find best matching segment range
            best_start = transcript_segments[segment_idx].get('start', 0)
            best_end = best_start

            for i in range(segment_idx, min(segment_idx + 50, total_segments)):
                seg = transcript_segments[i]
                seg_words = set(seg.get('text', '').lower().split())

                if chunk_words & seg_words:
                    best_end = seg.get('start', 0) + seg.get('duration', 0)
                    if i > segment_idx:
                        segment_idx = i

            timestamps.append((int(best_start), int(best_end)))

        return timestamps

    def chunk(
        self,
        content: str,
        transcript_segments: Optional[List[Dict]] = None,
        video_duration: int = 0
    ) -> List[Chunk]:
        """
        Chunk content into fixed-size pieces.

        Args:
            content: Text to chunk
            transcript_segments: Optional segments for timestamp estimation
            video_duration: Video duration for timestamp estimation

        Returns:
            List of Chunk objects
        """
        text_chunks = self.split_text(content)
        timestamps = self.estimate_timestamps(text_chunks, transcript_segments, video_duration)

        chunks = []
        for idx, (text, (start, end)) in enumerate(zip(text_chunks, timestamps)):
            chunk = Chunk(
                chunk_index=idx,
                chunk_text=text,
                start_timestamp=start,
                end_timestamp=end,
                chunk_length=len(text),
                chunk_tokens=self.count_units(text) if self.use_tokens else None
            )
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} fixed-size chunks")
        return chunks

    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return f"fixed_size_{self.chunk_size}"