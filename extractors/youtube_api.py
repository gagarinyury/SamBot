"""
YouTube Data API v3 Client
More reliable alternative to pytube for getting video metadata.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

import aiohttp
import isodate

from config import get_config

logger = logging.getLogger(__name__)

@dataclass
class YouTubeVideoMetadata:
    """Video metadata from YouTube Data API v3."""
    video_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    published_at: datetime
    duration: int  # in seconds
    view_count: int
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    thumbnail_url: Optional[str] = None
    tags: list = None

class YouTubeDataAPI:
    """YouTube Data API v3 client."""
    
    def __init__(self):
        self.config = get_config()
        self.api_key = self.config.youtube.api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
        if not self.api_key:
            logger.warning("YouTube API key not configured, falling back to pytube")
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([^&\n?#]+)',
            r'youtube\.com/embed/([^&\n?#]+)',
            r'youtube\.com/v/([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def get_video_metadata(self, video_id: str) -> Optional[YouTubeVideoMetadata]:
        """
        Get video metadata using YouTube Data API v3.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            YouTubeVideoMetadata object or None if failed
        """
        if not self.api_key:
            logger.warning("YouTube API key not available")
            return None
        
        url = f"{self.base_url}/videos"
        params = {
            'key': self.api_key,
            'id': video_id,
            'part': 'snippet,contentDetails,statistics'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"YouTube API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if not data.get('items'):
                        logger.error(f"Video {video_id} not found")
                        return None
                    
                    item = data['items'][0]
                    return self._parse_video_data(video_id, item)
                    
        except Exception as e:
            logger.error(f"Error fetching video metadata: {e}")
            return None
    
    def _parse_video_data(self, video_id: str, item: Dict[str, Any]) -> YouTubeVideoMetadata:
        """Parse video data from API response."""
        snippet = item['snippet']
        content_details = item['contentDetails']
        statistics = item.get('statistics', {})
        
        # Parse duration (ISO 8601 format)
        duration_iso = content_details.get('duration', 'PT0S')
        duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())
        
        # Parse published date
        published_at = datetime.fromisoformat(
            snippet['publishedAt'].replace('Z', '+00:00')
        )
        
        # Get best thumbnail
        thumbnails = snippet.get('thumbnails', {})
        thumbnail_url = None
        for quality in ['maxres', 'high', 'medium', 'default']:
            if quality in thumbnails:
                thumbnail_url = thumbnails[quality]['url']
                break
        
        return YouTubeVideoMetadata(
            video_id=video_id,
            title=snippet.get('title', ''),
            description=snippet.get('description', ''),
            channel_title=snippet.get('channelTitle', ''),
            channel_id=snippet.get('channelId', ''),
            published_at=published_at,
            duration=duration_seconds,
            view_count=int(statistics.get('viewCount', 0)),
            like_count=int(statistics.get('likeCount', 0)) if statistics.get('likeCount') else None,
            comment_count=int(statistics.get('commentCount', 0)) if statistics.get('commentCount') else None,
            thumbnail_url=thumbnail_url,
            tags=snippet.get('tags', [])
        )
    
    async def get_video_metadata_from_url(self, url: str) -> Optional[YouTubeVideoMetadata]:
        """
        Get video metadata from YouTube URL.
        
        Args:
            url: YouTube URL
            
        Returns:
            YouTubeVideoMetadata object or None if failed
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.error(f"Could not extract video ID from URL: {url}")
            return None
        
        return await self.get_video_metadata(video_id)