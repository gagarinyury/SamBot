"""
Rate limiter for YouTube API requests.
Limits: 1 video per minute (60 videos/hour) - conservative and safe.
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter to prevent YouTube blocking."""
    
    def __init__(self, requests_per_minute: int = 1):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # seconds between requests
        self.last_request_time: Optional[float] = None
        
    def wait_if_needed(self) -> float:
        """
        Wait if necessary to respect rate limit.
        Returns: seconds waited
        """
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return 0.0
            
        elapsed = time.time() - self.last_request_time
        
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            logger.info(f"Rate limit: waiting {wait_time:.1f}s before next request")
            time.sleep(wait_time)
            self.last_request_time = time.time()
            return wait_time
        else:
            self.last_request_time = time.time()
            return 0.0
            
    def reset(self):
        """Reset the rate limiter."""
        self.last_request_time = None


# Global rate limiter instance
youtube_rate_limiter = RateLimiter(requests_per_minute=1)
