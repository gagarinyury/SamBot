"""
Web Content Extractor
Extracts articles and content from web pages using newspaper3k and BeautifulSoup.
"""

import asyncio
import logging
import re
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import aiohttp
import validators
from langdetect import detect, DetectorFactory
from newspaper import Article, Config as NewspaperConfig
from bs4 import BeautifulSoup
from readability import Document
from fake_useragent import UserAgent

from config import get_config
from database.manager import get_database_manager

# Configure logging
logger = logging.getLogger(__name__)

# Make language detection deterministic
DetectorFactory.seed = 0

class ExtractionMethod(Enum):
    """Method used for content extraction."""
    NEWSPAPER = "newspaper"
    BEAUTIFULSOUP = "beautifulsoup"
    READABILITY = "readability"
    COMBINED = "combined"

class ExtractionStatus(Enum):
    """Status of content extraction."""
    SUCCESS = "success"
    NO_CONTENT = "no_content"
    INVALID_URL = "invalid_url"
    ACCESS_DENIED = "access_denied"
    ROBOTS_BLOCKED = "robots_blocked"
    TIMEOUT = "timeout"
    TOO_LARGE = "too_large"
    UNSUPPORTED_FORMAT = "unsupported_format"
    ERROR = "error"

@dataclass
class WebArticleInfo:
    """Web article metadata."""
    url: str
    title: str
    authors: List[str]
    publish_date: Optional[datetime]
    top_image: Optional[str]
    meta_description: Optional[str]
    meta_keywords: List[str]
    language: Optional[str] = None
    domain: Optional[str] = None
    word_count: int = 0

@dataclass
class ExtractionRequest:
    """Request data for web content extraction."""
    url: str
    preferred_languages: List[str] = None
    max_content_length: int = 100000  # 100KB limit
    user_id: Optional[int] = None
    follow_redirects: bool = True
    respect_robots: bool = True
    
    def __post_init__(self):
        if self.preferred_languages is None:
            self.preferred_languages = ['fr', 'en', 'ru']  # France market default

@dataclass
class ExtractionResponse:
    """Response from web content extraction."""
    status: ExtractionStatus
    content: str
    article_info: Optional[WebArticleInfo] = None
    extraction_method: ExtractionMethod = ExtractionMethod.NEWSPAPER
    processing_time: float = 0.0
    error_message: str = ""
    detected_language: Optional[str] = None
    final_url: Optional[str] = None  # After redirects
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

class WebExtractorError(Exception):
    """Web extractor specific errors."""
    pass

class ContentUnavailableError(WebExtractorError):
    """Content is not available for extraction."""
    pass

class AccessDeniedError(WebExtractorError):
    """Access to content is denied."""
    pass

class WebExtractor:
    """
    Advanced web content extractor with multiple extraction methods,
    content validation, and comprehensive error handling.
    """
    
    def __init__(self, database_manager=None):
        self.config = get_config()
        self.db = database_manager or get_database_manager()
        
        # Web-specific configuration
        self.web_config = self.config.web
        
        # User agent rotation
        self.ua = UserAgent()
        
        # Newspaper configuration
        self.newspaper_config = NewspaperConfig()
        self.newspaper_config.browser_user_agent = self.web_config.user_agent
        self.newspaper_config.request_timeout = self.web_config.request_timeout
        self.newspaper_config.number_threads = 1  # Async handling
        
        # Blocked file extensions
        self.blocked_extensions = {
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
            'zip', 'rar', 'tar', 'gz', '7z',
            'mp3', 'mp4', 'avi', 'mov', 'wmv', 'flv',
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg',
            'exe', 'msi', 'dmg', 'deb', 'rpm'
        }
        
        # Statistics
        self.stats = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'newspaper_used': 0,
            'beautifulsoup_used': 0,
            'readability_used': 0,
            'robots_blocked': 0,
        }
        
        logger.info("Web extractor initialized")

    def validate_web_url(self, url: str) -> bool:
        """
        Validate if URL is a valid web URL (not YouTube or other video platforms).
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid web URL, False otherwise
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
        
        # Parse URL for additional checks
        try:
            parsed = urlparse(url)
            
            # Check protocol
            if parsed.scheme not in ('http', 'https'):
                return False
            
            # Check for blocked domains (video platforms, etc.)
            blocked_domains = {
                'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
                'twitch.tv', 'tiktok.com', 'instagram.com', 'twitter.com',
                'facebook.com', 'linkedin.com'
            }
            
            domain = parsed.netloc.lower()
            for blocked in blocked_domains:
                if blocked in domain:
                    return False
            
            # Check file extension
            path = parsed.path.lower()
            if '.' in path:
                ext = path.split('.')[-1]
                if ext in self.blocked_extensions:
                    return False
            
            return True
            
        except Exception:
            return False

    def get_random_user_agent(self) -> str:
        """Get random user agent for request."""
        try:
            return self.ua.random
        except Exception:
            return self.web_config.user_agent

    async def check_robots_txt(self, url: str, user_agent: str = '*') -> bool:
        """
        Check if URL is allowed by robots.txt.
        
        Args:
            url: URL to check
            user_agent: User agent to check for
            
        Returns:
            True if allowed, False if blocked
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(robots_url) as response:
                    if response.status == 200:
                        robots_content = await response.text()
                        
                        # Simple robots.txt parsing
                        rp = RobotFileParser()
                        rp.set_url(robots_url)
                        # Convert to list of lines for set_url to work
                        rp.read()
                        return rp.can_fetch(user_agent, url)
                    
            # If robots.txt not found or error, allow access
            return True
            
        except Exception as e:
            logger.debug(f"Robots.txt check failed for {url}: {e}")
            return True  # Default to allow if check fails

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
            if len(content.strip()) < 100:
                return None
                
            language = detect(content)
            logger.debug(f"Detected language: {language}")
            return language
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return None

    async def extract_with_newspaper(self, url: str) -> Tuple[str, WebArticleInfo]:
        """
        Extract content using newspaper3k.
        
        Args:
            url: URL to extract
            
        Returns:
            Tuple of (content, article_info)
        """
        try:
            article = Article(url, config=self.newspaper_config)
            
            # Download and parse
            article.download()
            article.parse()
            
            # Extract article info
            article_info = WebArticleInfo(
                url=url,
                title=article.title or "Unknown Title",
                authors=article.authors or [],
                publish_date=article.publish_date,
                top_image=article.top_image,
                meta_description=article.meta_description,
                meta_keywords=article.meta_keywords or [],
                domain=urlparse(url).netloc,
                word_count=len(article.text.split()) if article.text else 0
            )
            
            content = article.text
            if not content or len(content.strip()) < 50:
                raise ContentUnavailableError("Article content is empty or too short")
                
            return content, article_info
            
        except Exception as e:
            logger.error(f"Newspaper extraction failed for {url}: {e}")
            raise ContentUnavailableError(f"Newspaper extraction failed: {e}")

    async def extract_with_beautifulsoup(self, url: str, session: aiohttp.ClientSession) -> Tuple[str, WebArticleInfo]:
        """
        Extract content using BeautifulSoup + readability.
        
        Args:
            url: URL to extract
            session: HTTP session
            
        Returns:
            Tuple of (content, article_info)
        """
        try:
            headers = {
                'User-Agent': self.get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise AccessDeniedError(f"HTTP {response.status}")
                
                html = await response.text()
                
            # Use readability to extract main content
            doc = Document(html)
            content_html = doc.summary()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(content_html, 'html.parser')
            
            # Extract text content
            content = soup.get_text(separator=' ', strip=True)
            
            # Clean up content
            content = re.sub(r'\s+', ' ', content)
            content = content.strip()
            
            if not content or len(content.strip()) < 50:
                raise ContentUnavailableError("Extracted content is empty or too short")
            
            # Extract basic article info from original HTML
            original_soup = BeautifulSoup(html, 'html.parser')
            
            title = "Unknown Title"
            if original_soup.title:
                title = original_soup.title.string or title
            
            # Try to get meta description
            meta_desc = None
            desc_tag = original_soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                meta_desc = desc_tag.get('content')
            
            article_info = WebArticleInfo(
                url=url,
                title=title,
                authors=[],  # Hard to extract reliably
                publish_date=None,  # Hard to extract reliably
                top_image=None,
                meta_description=meta_desc,
                meta_keywords=[],
                domain=urlparse(url).netloc,
                word_count=len(content.split())
            )
            
            return content, article_info
            
        except Exception as e:
            logger.error(f"BeautifulSoup extraction failed for {url}: {e}")
            raise ContentUnavailableError(f"BeautifulSoup extraction failed: {e}")

    async def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        """
        Extract content from web page.
        
        Args:
            request: Extraction request
            
        Returns:
            Extraction response with content and metadata
        """
        start_time = time.time()
        self.stats['total_extractions'] += 1
        
        try:
            # Validate URL
            if not self.validate_web_url(request.url):
                return ExtractionResponse(
                    status=ExtractionStatus.INVALID_URL,
                    content="",
                    error_message="Invalid or unsupported URL",
                    processing_time=time.time() - start_time
                )
            
            url = request.url
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Check robots.txt if required
            if request.respect_robots:
                user_agent = self.get_random_user_agent()
                robots_allowed = await self.check_robots_txt(url, user_agent)
                if not robots_allowed:
                    self.stats['robots_blocked'] += 1
                    await self.db.log_event(
                        event_type="web_extraction_robots_blocked",
                        user_id=request.user_id,
                        data={"url": url}
                    )
                    return ExtractionResponse(
                        status=ExtractionStatus.ROBOTS_BLOCKED,
                        content="",
                        error_message="Access blocked by robots.txt",
                        processing_time=time.time() - start_time
                    )
            
            # Try newspaper3k first
            content = None
            article_info = None
            extraction_method = ExtractionMethod.NEWSPAPER
            final_url = url
            
            try:
                content, article_info = await self.extract_with_newspaper(url)
                self.stats['newspaper_used'] += 1
                
            except ContentUnavailableError:
                # Fallback to BeautifulSoup + readability
                logger.info(f"Newspaper failed for {url}, trying BeautifulSoup")
                
                timeout = aiohttp.ClientTimeout(
                    total=self.web_config.request_timeout,
                    connect=self.web_config.connect_timeout
                )
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    try:
                        content, article_info = await self.extract_with_beautifulsoup(url, session)
                        extraction_method = ExtractionMethod.BEAUTIFULSOUP
                        self.stats['beautifulsoup_used'] += 1
                        
                    except Exception as e:
                        raise ContentUnavailableError(f"All extraction methods failed: {e}")
            
            # Check content length limit
            if len(content) > request.max_content_length:
                content = content[:request.max_content_length]
                logger.warning(f"Content truncated to {request.max_content_length} chars for {url}")
            
            # Detect content language
            detected_language = self.detect_content_language(content)
            if detected_language:
                article_info.language = detected_language
            
            # Update statistics
            self.stats['successful_extractions'] += 1
            
            # Log successful extraction
            await self.db.log_event(
                event_type="web_extraction_success",
                user_id=request.user_id,
                data={
                    "url": url,
                    "final_url": final_url,
                    "extraction_method": extraction_method.value,
                    "content_length": len(content),
                    "detected_language": detected_language,
                    "title": article_info.title,
                    "domain": article_info.domain
                }
            )
            
            return ExtractionResponse(
                status=ExtractionStatus.SUCCESS,
                content=content,
                article_info=article_info,
                extraction_method=extraction_method,
                processing_time=time.time() - start_time,
                detected_language=detected_language,
                final_url=final_url
            )
            
        except ContentUnavailableError as e:
            self.stats['failed_extractions'] += 1
            await self.db.log_error(
                error_type="web_content_unavailable",
                error_message=str(e),
                user_id=request.user_id,
                url=request.url
            )
            return ExtractionResponse(
                status=ExtractionStatus.NO_CONTENT,
                content="",
                error_message=str(e),
                processing_time=time.time() - start_time
            )
            
        except AccessDeniedError as e:
            self.stats['failed_extractions'] += 1
            return ExtractionResponse(
                status=ExtractionStatus.ACCESS_DENIED,
                content="",
                error_message=str(e),
                processing_time=time.time() - start_time
            )
            
        except asyncio.TimeoutError:
            self.stats['failed_extractions'] += 1
            return ExtractionResponse(
                status=ExtractionStatus.TIMEOUT,
                content="",
                error_message="Request timeout",
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            self.stats['failed_extractions'] += 1
            logger.error(f"Unexpected error in web extraction: {e}")
            await self.db.log_error(
                error_type="web_extraction_error",
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
            'newspaper_rate': (
                (self.stats['newspaper_used'] / self.stats['successful_extractions'] * 100)
                if self.stats['successful_extractions'] > 0 else 0
            ),
            'beautifulsoup_rate': (
                (self.stats['beautifulsoup_used'] / self.stats['successful_extractions'] * 100)
                if self.stats['successful_extractions'] > 0 else 0
            )
        }

# Global instance
_web_extractor = None

def get_web_extractor(database_manager=None) -> WebExtractor:
    """Get global web extractor instance."""
    global _web_extractor
    if _web_extractor is None:
        _web_extractor = WebExtractor(database_manager)
    return _web_extractor

# Convenience function
async def extract_web_content(
    url: str,
    preferred_languages: List[str] = None,
    max_content_length: int = 100000,
    user_id: Optional[int] = None,
    follow_redirects: bool = True,
    respect_robots: bool = True
) -> ExtractionResponse:
    """
    Convenience function to extract web content.
    
    Args:
        url: Web page URL
        preferred_languages: Preferred content languages
        max_content_length: Maximum content length in characters
        user_id: User ID for logging
        follow_redirects: Whether to follow HTTP redirects
        respect_robots: Whether to respect robots.txt
        
    Returns:
        Extraction response
    """
    extractor = get_web_extractor()
    request = ExtractionRequest(
        url=url,
        preferred_languages=preferred_languages,
        max_content_length=max_content_length,
        user_id=user_id,
        follow_redirects=follow_redirects,
        respect_robots=respect_robots
    )
    return await extractor.extract(request)