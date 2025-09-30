"""
YouTube Video Chapters Extractor
Extracts chapters from video descriptions for better content segmentation.
"""

import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class VideoChapter:
    """Represents a single video chapter."""
    time: str           # Original time string (e.g., "1:23")
    title: str          # Chapter title
    start_seconds: int  # Start time in seconds
    end_seconds: Optional[int] = None  # End time (set when processing full list)

class ChapterExtractor:
    """Extracts chapters from YouTube video descriptions."""
    
    def __init__(self):
        # Common patterns for time stamps in descriptions
        self.time_patterns = [
            # 00:00 Title, 1:23 Title, 1:23:45 Title
            r'^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*(.+)$',
            r'^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$',
            r'^(\d{1,2}:\d{2}(?::\d{2})?)\s*[\.]\s*(.+)$',
            # [00:00] Title, (1:23) Title
            r'^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)$',
            r'^\((\d{1,2}:\d{2}(?::\d{2})?)\)\s*(.+)$',
        ]
    
    def extract_chapters(self, description: str) -> List[VideoChapter]:
        """
        Extract chapters from video description.
        
        Args:
            description: Video description text
            
        Returns:
            List of VideoChapter objects
        """
        if not description:
            return []
            
        lines = description.split('\n')
        chapters = []
        
        for line in lines:
            line = line.strip()
            if not line or len(line) > 200:  # Skip empty lines and very long lines
                continue
                
            chapter = self._parse_chapter_line(line)
            if chapter:
                chapters.append(chapter)
        
        # Set end times for chapters
        chapters = self._set_end_times(chapters)
        
        # Filter out invalid chapters
        chapters = self._filter_valid_chapters(chapters)
        
        logger.info(f"Extracted {len(chapters)} chapters from description")
        return chapters
    
    def _parse_chapter_line(self, line: str) -> Optional[VideoChapter]:
        """Parse a single line for chapter information."""
        for pattern in self.time_patterns:
            match = re.match(pattern, line)
            if match:
                time_str = match.group(1)
                title = match.group(2).strip()
                
                # Clean up title
                title = re.sub(r'^[-–—\.\s]+', '', title)  # Remove leading dashes/dots
                title = re.sub(r'[-–—\.\s]+$', '', title)  # Remove trailing dashes/dots
                
                if title and len(title) > 2:  # Must have meaningful title
                    start_seconds = self._time_to_seconds(time_str)
                    if start_seconds is not None:
                        return VideoChapter(
                            time=time_str,
                            title=title,
                            start_seconds=start_seconds
                        )
        
        return None
    
    def _time_to_seconds(self, time_str: str) -> Optional[int]:
        """Convert time string to seconds."""
        try:
            parts = time_str.split(':')
            if len(parts) == 2:  # mm:ss
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # hh:mm:ss
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            pass
        
        return None
    
    def _set_end_times(self, chapters: List[VideoChapter]) -> List[VideoChapter]:
        """Set end times for chapters based on next chapter start."""
        for i in range(len(chapters) - 1):
            chapters[i].end_seconds = chapters[i + 1].start_seconds
        
        # Last chapter has no end time (goes to video end)
        return chapters
    
    def _filter_valid_chapters(self, chapters: List[VideoChapter]) -> List[VideoChapter]:
        """Filter out invalid or suspicious chapters."""
        if not chapters:
            return []
        
        # Remove chapters that are too close together (< 10 seconds)
        filtered = [chapters[0]]  # Always keep first chapter
        
        for chapter in chapters[1:]:
            if chapter.start_seconds - filtered[-1].start_seconds >= 10:
                filtered.append(chapter)
        
        # Must have at least 2 chapters to be useful
        return filtered if len(filtered) >= 2 else []
    
    def get_chapter_segments(self, chapters: List[VideoChapter], video_duration: int) -> List[Dict]:
        """
        Get chapter segments for content processing.
        
        Args:
            chapters: List of chapters
            video_duration: Total video duration in seconds
            
        Returns:
            List of dictionaries with segment info
        """
        if not chapters:
            return []
        
        segments = []
        
        for i, chapter in enumerate(chapters):
            end_time = chapter.end_seconds
            if end_time is None:  # Last chapter
                end_time = video_duration
            
            # Skip very short segments (< 30 seconds)
            duration = end_time - chapter.start_seconds
            if duration >= 30:
                segments.append({
                    'index': i + 1,
                    'title': chapter.title,
                    'start_time': chapter.start_seconds,
                    'end_time': end_time,
                    'duration': duration,
                    'time_range': f"{self._seconds_to_time(chapter.start_seconds)} - {self._seconds_to_time(end_time)}"
                })
        
        return segments
    
    def _seconds_to_time(self, seconds: int) -> str:
        """Convert seconds back to time string."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def should_use_chapters(self, chapters: List[VideoChapter], video_duration: int) -> bool:
        """
        Determine if chapters should be used for processing.
        
        Args:
            chapters: Extracted chapters
            video_duration: Total video duration in seconds
            
        Returns:
            True if chapters are worth using
        """
        if not chapters or len(chapters) < 2:
            return False
        
        # Only use chapters for videos longer than 10 minutes
        if video_duration < 600:
            return False
        
        # Check if chapters cover most of the video
        last_chapter_start = chapters[-1].start_seconds
        coverage = last_chapter_start / video_duration
        
        return coverage > 0.5  # Chapters should cover at least 50% of video

# Global instance
_chapter_extractor = None

def get_chapter_extractor() -> ChapterExtractor:
    """Get global chapter extractor instance."""
    global _chapter_extractor
    if _chapter_extractor is None:
        _chapter_extractor = ChapterExtractor()
    return _chapter_extractor

# Convenience function
def extract_video_chapters(description: str, video_duration: int = 0) -> Dict:
    """
    Extract chapters from video description.
    
    Args:
        description: Video description
        video_duration: Video duration in seconds (optional)
        
    Returns:
        Dict with chapters info and segments
    """
    extractor = get_chapter_extractor()
    chapters = extractor.extract_chapters(description)
    
    # Convert VideoChapter dataclasses to dicts for JSON serialization
    chapters_dicts = [
        {
            'time': ch.time,
            'title': ch.title,
            'start_seconds': ch.start_seconds,
            'end_seconds': ch.end_seconds
        }
        for ch in chapters
    ]

    result = {
        'has_chapters': len(chapters) > 0,
        'chapter_count': len(chapters),
        'chapters': chapters_dicts,
        'segments': [],
        'should_use_chapters': False
    }
    
    if chapters and video_duration > 0:
        result['segments'] = extractor.get_chapter_segments(chapters, video_duration)
        result['should_use_chapters'] = extractor.should_use_chapters(chapters, video_duration)
    
    return result