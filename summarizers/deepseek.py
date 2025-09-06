"""
DeepSeek AI Summarizer
Advanced multilingual summarization with caching, retry logic, and monitoring.
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

import aiohttp
from openai import AsyncOpenAI

from config import get_config
from database.manager import get_database_manager

# Configure logging
logger = logging.getLogger(__name__)

class SummaryLength(Enum):
    """Summary length options."""
    BRIEF = "brief"
    MEDIUM = "medium" 
    DETAILED = "detailed"

class ContentType(Enum):
    """Content type options."""
    YOUTUBE = "youtube"
    WEB = "web"
    UNIVERSAL = "universal"

@dataclass
class SummaryRequest:
    """Request data for summarization."""
    content: str
    content_type: ContentType
    target_language: str = "fr"  # Default to French for France market
    summary_length: SummaryLength = SummaryLength.MEDIUM
    custom_prompt: Optional[str] = None
    user_id: Optional[int] = None
    original_url: Optional[str] = None

@dataclass
class SummaryResponse:
    """Response from summarization."""
    summary: str
    tokens_used: int
    language: str
    length: SummaryLength
    processing_time: float
    cached: bool = False
    prompt_used: str = ""
    content_hash: str = ""
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

class DeepSeekError(Exception):
    """DeepSeek API specific errors."""
    pass

class RateLimitError(DeepSeekError):
    """Rate limit exceeded error."""
    pass

class DeepSeekSummarizer:
    """
    Advanced DeepSeek AI Summarizer with multilingual support,
    caching, retry logic, and comprehensive monitoring.
    """
    
    def __init__(self, database_manager=None):
        self.config = get_config()
        self.db = database_manager
        
        # Initialize OpenAI client for DeepSeek API
        self.client = AsyncOpenAI(
            api_key=self.config.ai.deepseek_api_key,
            base_url="https://api.deepseek.com"  # Official DeepSeek API endpoint (verified 2025)
        )
        
        # Rate limiting
        self.rate_limiter = {
            'requests': [],
            'max_per_minute': 60,
            'max_per_hour': 1000
        }
        
        # Retry configuration
        self.retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 60.0,
            'exponential_base': 2
        }
        
        # Prompt templates cache
        self._prompt_cache = {}
        self._cache_expiry = {}
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_tokens': 0,
            'errors': 0,
            'avg_response_time': 0
        }

    async def summarize(self, request: SummaryRequest) -> SummaryResponse:
        """
        Main summarization method with caching and error handling.
        
        Args:
            request: SummaryRequest with content and parameters
            
        Returns:
            SummaryResponse with summary and metadata
        """
        start_time = time.time()
        
        try:
            # Generate content hash for caching
            content_hash = self._generate_hash(request.content, request.target_language, request.summary_length.value)
            
            # Check cache first
            cached_summary = await self._get_cached_summary(content_hash)
            if cached_summary:
                self.stats['cache_hits'] += 1
                logger.info(f"Cache hit for content hash: {content_hash[:16]}...")
                
                return SummaryResponse(
                    summary=cached_summary['summary'],
                    tokens_used=cached_summary['tokens_used'],
                    language=cached_summary['summary_language'],
                    length=SummaryLength(cached_summary['summary_length']),
                    processing_time=time.time() - start_time,
                    cached=True,
                    content_hash=content_hash
                )
            
            self.stats['cache_misses'] += 1
            
            # Check rate limits
            await self._check_rate_limits()
            
            # Get appropriate prompt template
            prompt = await self._get_prompt_template(request)
            
            # Generate summary with retry logic
            summary_text, tokens_used = await self._generate_summary_with_retry(
                content=request.content,
                prompt=prompt,
                target_language=request.target_language
            )
            
            processing_time = time.time() - start_time
            
            # Create response
            response = SummaryResponse(
                summary=summary_text,
                tokens_used=tokens_used,
                language=request.target_language,
                length=request.summary_length,
                processing_time=processing_time,
                cached=False,
                prompt_used=prompt,
                content_hash=content_hash
            )
            
            # Cache the result
            await self._cache_summary(request, response)
            
            # Update statistics
            self._update_stats(tokens_used, processing_time)
            
            logger.info(f"Summary generated: {tokens_used} tokens, {processing_time:.2f}s")
            
            return response
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Summarization failed: {str(e)}", exc_info=True)
            raise DeepSeekError(f"Summarization failed: {str(e)}") from e

    async def _generate_summary_with_retry(self, content: str, prompt: str, target_language: str) -> Tuple[str, int]:
        """Generate summary with exponential backoff retry logic."""
        last_exception = None
        
        for attempt in range(self.retry_config['max_retries']):
            try:
                return await self._call_deepseek_api(content, prompt, target_language)
                
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # Rate limit
                    delay = min(
                        self.retry_config['base_delay'] * (self.retry_config['exponential_base'] ** attempt),
                        self.retry_config['max_delay']
                    )
                    logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    last_exception = e
                    continue
                else:
                    raise DeepSeekError(f"API error {e.status}: {e.message}") from e
                    
            except Exception as e:
                if attempt == self.retry_config['max_retries'] - 1:
                    raise
                    
                delay = self.retry_config['base_delay'] * (self.retry_config['exponential_base'] ** attempt)
                logger.warning(f"Request failed, retrying in {delay}s: {str(e)}")
                await asyncio.sleep(delay)
                last_exception = e
        
        raise DeepSeekError(f"All retry attempts failed. Last error: {str(last_exception)}") from last_exception

    async def _call_deepseek_api(self, content: str, prompt: str, target_language: str) -> Tuple[str, int]:
        """Make actual API call to DeepSeek."""
        try:
            # Prepare the messages
            messages = [
                {
                    "role": "system", 
                    "content": f"You are an expert summarizer. Always respond in {self._get_language_name(target_language)}. Create accurate, well-structured summaries that capture the key points and insights."
                },
                {
                    "role": "user",
                    "content": prompt.format(content=content[:self.config.ai.max_text_length])
                }
            ]
            
            # Make API call
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.3,  # Consistent summaries
                max_tokens=2000,  # Reasonable summary length
                stream=False
            )
            
            summary = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens
            
            # Validate response
            if not summary or len(summary) < 10:
                raise DeepSeekError("Generated summary is too short or empty")
            
            return summary, tokens_used
            
        except Exception as e:
            logger.error(f"DeepSeek API call failed: {str(e)}")
            raise

    async def _get_prompt_template(self, request: SummaryRequest) -> str:
        """Get appropriate prompt template for the request."""
        if request.custom_prompt:
            return request.custom_prompt
            
        # Cache key for prompt templates
        cache_key = f"{request.content_type.value}_{request.target_language}_{request.summary_length.value}"
        
        # Check cache first
        if cache_key in self._prompt_cache:
            if time.time() < self._cache_expiry.get(cache_key, 0):
                return self._prompt_cache[cache_key]
        
        # Get from database
        if self.db:
            prompt = await self.db.get_prompt_template(
                content_type=request.content_type.value,
                language=request.target_language,
                length=request.summary_length.value
            )
            
            if prompt:
                # Cache for 1 hour
                self._prompt_cache[cache_key] = prompt
                self._cache_expiry[cache_key] = time.time() + 3600
                return prompt
        
        # Fallback to default prompts
        return self._get_default_prompt(request)

    def _get_default_prompt(self, request: SummaryRequest) -> str:
        """Get default prompt templates as fallback."""
        lang_name = self._get_language_name(request.target_language)
        content_type = request.content_type.value
        
        if request.target_language == "fr":
            if content_type == "youtube":
                if request.summary_length == SummaryLength.BRIEF:
                    return "Créez un résumé bref (2-3 phrases) de cette vidéo YouTube en français :\n\n{content}\n\nRésumé :"
                else:
                    return "Analysez cette transcription YouTube et créez un résumé détaillé en français avec les points clés, les insights principaux, et les conclusions importantes :\n\n{content}\n\nRésumé détaillé :"
            else:
                if request.summary_length == SummaryLength.BRIEF:
                    return "Résumez cet article web en 2-3 phrases principales en français :\n\n{content}\n\nRésumé :"
                else:
                    return "Analysez cet article et fournissez un résumé détaillé en français avec les points principaux, les arguments clés, et les conclusions :\n\n{content}\n\nRésumé détaillé :"
        
        elif request.target_language == "en":
            if content_type == "youtube":
                if request.summary_length == SummaryLength.BRIEF:
                    return "Create a brief summary (2-3 sentences) of this YouTube video in English:\n\n{content}\n\nSummary:"
                else:
                    return "Analyze this YouTube transcript and create a detailed summary in English with key points, main insights, and important conclusions:\n\n{content}\n\nDetailed summary:"
            else:
                if request.summary_length == SummaryLength.BRIEF:
                    return "Summarize this web article in 2-3 main sentences in English:\n\n{content}\n\nSummary:"
                else:
                    return "Analyze this article and provide a detailed summary in English with main points, key arguments, and conclusions:\n\n{content}\n\nDetailed summary:"
        
        elif request.target_language == "ru":
            if content_type == "youtube":
                if request.summary_length == SummaryLength.BRIEF:
                    return "Создайте краткое резюме (2-3 предложения) этого YouTube видео на русском языке:\n\n{content}\n\nКраткое резюме:"
                else:
                    return "Проанализируйте эту расшифровку YouTube и создайте подробное резюме на русском языке с ключевыми моментами, основными выводами и важными заключениями:\n\n{content}\n\nПодробное резюме:"
            else:
                if request.summary_length == SummaryLength.BRIEF:
                    return "Резюмируйте эту веб-статью в 2-3 основных предложениях на русском языке:\n\n{content}\n\nКраткое резюме:"
                else:
                    return "Проанализируйте эту статью и предоставьте подробное резюме на русском языке с основными моментами, ключевыми аргументами и выводами:\n\n{content}\n\nПодробное резюме:"
        
        # Default fallback to English
        return "Summarize this content in a clear and concise manner:\n\n{content}\n\nSummary:"

    async def _get_cached_summary(self, content_hash: str) -> Optional[Dict]:
        """Get cached summary from database."""
        if not self.db:
            return None
            
        try:
            return await self.db.get_cached_summary(content_hash)
        except Exception as e:
            logger.warning(f"Failed to get cached summary: {str(e)}")
            return None

    async def _cache_summary(self, request: SummaryRequest, response: SummaryResponse):
        """Cache summary in database."""
        if not self.db:
            return
            
        try:
            await self.db.cache_summary(
                url_hash=response.content_hash,
                original_url=request.original_url,
                content_type=request.content_type.value,
                content_hash=response.content_hash,
                summary=response.summary,
                summary_language=response.language,
                summary_length=response.length.value,
                tokens_used=response.tokens_used,
                created_by_user_id=request.user_id
            )
        except Exception as e:
            logger.warning(f"Failed to cache summary: {str(e)}")

    async def _check_rate_limits(self):
        """Check and enforce rate limits."""
        now = time.time()
        
        # Clean old requests
        self.rate_limiter['requests'] = [
            req_time for req_time in self.rate_limiter['requests']
            if now - req_time < 3600  # Keep last hour
        ]
        
        # Check minute limit
        recent_requests = [
            req_time for req_time in self.rate_limiter['requests']
            if now - req_time < 60
        ]
        
        if len(recent_requests) >= self.rate_limiter['max_per_minute']:
            raise RateLimitError("Rate limit exceeded: too many requests per minute")
            
        # Check hourly limit
        if len(self.rate_limiter['requests']) >= self.rate_limiter['max_per_hour']:
            raise RateLimitError("Rate limit exceeded: too many requests per hour")
        
        # Record this request
        self.rate_limiter['requests'].append(now)

    def _generate_hash(self, content: str, language: str, length: str) -> str:
        """Generate hash for content caching."""
        hash_input = f"{content}{language}{length}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()

    def _get_language_name(self, code: str) -> str:
        """Get language name for prompts."""
        language_names = {
            'fr': 'French',
            'en': 'English', 
            'ru': 'Russian'
        }
        return language_names.get(code, 'English')

    def _update_stats(self, tokens_used: int, processing_time: float):
        """Update internal statistics."""
        self.stats['total_requests'] += 1
        self.stats['total_tokens'] += tokens_used
        
        # Update average response time
        total_time = self.stats['avg_response_time'] * (self.stats['total_requests'] - 1)
        self.stats['avg_response_time'] = (total_time + processing_time) / self.stats['total_requests']

    def get_stats(self) -> Dict:
        """Get current statistics."""
        cache_total = self.stats['cache_hits'] + self.stats['cache_misses']
        cache_rate = (self.stats['cache_hits'] / cache_total * 100) if cache_total > 0 else 0
        
        return {
            **self.stats,
            'cache_hit_rate': round(cache_rate, 2),
            'error_rate': round((self.stats['errors'] / max(self.stats['total_requests'], 1)) * 100, 2)
        }

    async def health_check(self) -> Dict[str, Union[bool, str, float]]:
        """Check API health and connectivity."""
        try:
            start_time = time.time()
            
            # Test with minimal request
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
            
            response_time = time.time() - start_time
            
            return {
                'status': True,
                'response_time': round(response_time, 3),
                'message': 'API is healthy'
            }
            
        except Exception as e:
            return {
                'status': False,
                'response_time': 0,
                'message': f'API health check failed: {str(e)}'
            }

# Global instance
_summarizer_instance = None

def get_summarizer(database_manager=None) -> DeepSeekSummarizer:
    """Get global DeepSeek summarizer instance."""
    global _summarizer_instance
    if _summarizer_instance is None:
        if database_manager is None:
            database_manager = get_database_manager()
        _summarizer_instance = DeepSeekSummarizer(database_manager)
    return _summarizer_instance

# Convenience functions
async def summarize_content(
    content: str,
    content_type: str = "web",
    target_language: str = "fr",
    summary_length: str = "medium",
    user_id: Optional[int] = None,
    original_url: Optional[str] = None,
    database_manager=None
) -> SummaryResponse:
    """Convenience function for summarizing content."""
    summarizer = get_summarizer(database_manager)
    
    request = SummaryRequest(
        content=content,
        content_type=ContentType(content_type),
        target_language=target_language,
        summary_length=SummaryLength(summary_length),
        user_id=user_id,
        original_url=original_url
    )
    
    return await summarizer.summarize(request)