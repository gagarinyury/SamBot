"""
Unit tests for DeepSeek Summarizer.
Tests core functionality without making actual API calls.
"""

import pytest
import asyncio
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Import the module we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from summarizers.deepseek import (
    DeepSeekSummarizer,
    SummaryRequest,
    SummaryResponse,
    SummaryLength,
    ContentType,
    DeepSeekError,
    RateLimitError,
    get_summarizer,
    summarize_content
)

class TestDeepSeekSummarizer:
    """Test cases for DeepSeekSummarizer class."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.ai.deepseek_api_key = "test-api-key"
        config.ai.max_text_length = 50000
        return config

    @pytest.fixture
    def mock_db(self):
        """Mock database manager."""
        db = AsyncMock()
        db.get_cached_summary.return_value = None
        db.cache_summary.return_value = None
        db.get_prompt_template.return_value = None
        return db

    @pytest.fixture
    def summarizer(self, mock_config, mock_db):
        """Create summarizer instance with mocked dependencies."""
        with patch('summarizers.deepseek.get_config', return_value=mock_config):
            with patch('summarizers.deepseek.AsyncOpenAI'):
                return DeepSeekSummarizer(mock_db)

    def test_init(self, summarizer):
        """Test summarizer initialization."""
        assert summarizer.db is not None
        assert summarizer.rate_limiter is not None
        assert summarizer.retry_config is not None
        assert summarizer.stats is not None
        assert summarizer._prompt_cache == {}

    def test_generate_hash(self, summarizer):
        """Test hash generation."""
        content = "test content"
        language = "en"
        length = "medium"
        
        hash1 = summarizer._generate_hash(content, language, length)
        hash2 = summarizer._generate_hash(content, language, length)
        hash3 = summarizer._generate_hash("different", language, length)
        
        # Same inputs should produce same hash
        assert hash1 == hash2
        # Different inputs should produce different hash
        assert hash1 != hash3
        # Should be valid SHA256 hex
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)

    def test_get_language_name(self, summarizer):
        """Test language name mapping."""
        assert summarizer._get_language_name('fr') == 'French'
        assert summarizer._get_language_name('en') == 'English'
        assert summarizer._get_language_name('ru') == 'Russian'
        assert summarizer._get_language_name('unknown') == 'English'  # Default

    def test_update_stats(self, summarizer):
        """Test statistics updating."""
        initial_requests = summarizer.stats['total_requests']
        initial_tokens = summarizer.stats['total_tokens']
        
        summarizer._update_stats(100, 1.5)
        
        assert summarizer.stats['total_requests'] == initial_requests + 1
        assert summarizer.stats['total_tokens'] == initial_tokens + 100
        assert summarizer.stats['avg_response_time'] > 0

    def test_get_stats(self, summarizer):
        """Test statistics retrieval."""
        # Add some mock data
        summarizer.stats['cache_hits'] = 5
        summarizer.stats['cache_misses'] = 10
        summarizer.stats['errors'] = 2
        summarizer.stats['total_requests'] = 15
        
        stats = summarizer.get_stats()
        
        assert stats['cache_hit_rate'] == 33.33  # 5/(5+10) * 100
        assert stats['error_rate'] == 13.33  # 2/15 * 100
        assert 'total_requests' in stats
        assert 'total_tokens' in stats

    @pytest.mark.asyncio
    async def test_check_rate_limits_within_limits(self, summarizer):
        """Test rate limiting when within limits."""
        # Should not raise exception when within limits
        await summarizer._check_rate_limits()
        assert len(summarizer.rate_limiter['requests']) == 1

    @pytest.mark.asyncio 
    async def test_check_rate_limits_exceeds_minute_limit(self, summarizer):
        """Test rate limiting when minute limit is exceeded."""
        import time
        current_time = time.time()
        
        # Fill up the minute limit
        summarizer.rate_limiter['requests'] = [current_time - 30] * 60
        
        with pytest.raises(RateLimitError, match="too many requests per minute"):
            await summarizer._check_rate_limits()

    def test_get_default_prompt_french_youtube_brief(self, summarizer):
        """Test default prompt generation for French YouTube brief."""
        request = SummaryRequest(
            content="test",
            content_type=ContentType.YOUTUBE,
            target_language="fr",
            summary_length=SummaryLength.BRIEF
        )
        
        prompt = summarizer._get_default_prompt(request)
        
        assert "Créez un résumé bref" in prompt
        assert "français" in prompt
        assert "{content}" in prompt

    def test_get_default_prompt_english_web_detailed(self, summarizer):
        """Test default prompt generation for English web detailed."""
        request = SummaryRequest(
            content="test",
            content_type=ContentType.WEB,
            target_language="en",
            summary_length=SummaryLength.DETAILED
        )
        
        prompt = summarizer._get_default_prompt(request)
        
        assert "detailed summary" in prompt
        assert "English" in prompt
        assert "{content}" in prompt

    @pytest.mark.asyncio
    async def test_get_cached_summary_hit(self, summarizer):
        """Test cache hit scenario."""
        mock_cached_data = {
            'summary': 'Cached summary',
            'tokens_used': 100,
            'summary_language': 'fr',
            'summary_length': 'medium'
        }
        summarizer.db.get_cached_summary.return_value = mock_cached_data
        
        result = await summarizer._get_cached_summary('test_hash')
        
        assert result == mock_cached_data
        summarizer.db.get_cached_summary.assert_called_once_with('test_hash')

    @pytest.mark.asyncio
    async def test_get_cached_summary_miss(self, summarizer):
        """Test cache miss scenario."""
        summarizer.db.get_cached_summary.return_value = None
        
        result = await summarizer._get_cached_summary('test_hash')
        
        assert result is None
        summarizer.db.get_cached_summary.assert_called_once_with('test_hash')

    @pytest.mark.asyncio
    async def test_cache_summary(self, summarizer):
        """Test summary caching."""
        request = SummaryRequest(
            content="test content",
            content_type=ContentType.YOUTUBE,
            original_url="https://youtube.com/watch?v=test"
        )
        
        response = SummaryResponse(
            summary="Test summary",
            tokens_used=100,
            language="fr",
            length=SummaryLength.MEDIUM,
            processing_time=1.5,
            content_hash="test_hash"
        )
        
        await summarizer._cache_summary(request, response)
        
        summarizer.db.cache_summary.assert_called_once()
        call_args = summarizer.db.cache_summary.call_args[1]
        assert call_args['summary'] == "Test summary"
        assert call_args['tokens_used'] == 100

    @pytest.mark.asyncio
    async def test_health_check_success(self, summarizer):
        """Test successful health check."""
        # Mock successful API response
        mock_response = MagicMock()
        summarizer.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await summarizer.health_check()
        
        assert result['status'] is True
        assert 'response_time' in result
        assert result['message'] == 'API is healthy'

    @pytest.mark.asyncio
    async def test_health_check_failure(self, summarizer):
        """Test failed health check."""
        # Mock API failure
        summarizer.client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        
        result = await summarizer.health_check()
        
        assert result['status'] is False
        assert result['response_time'] == 0
        assert 'API health check failed' in result['message']

class TestSummaryDataClasses:
    """Test data classes used in summarization."""

    def test_summary_request_creation(self):
        """Test SummaryRequest creation with defaults."""
        request = SummaryRequest(
            content="test content",
            content_type=ContentType.YOUTUBE
        )
        
        assert request.content == "test content"
        assert request.content_type == ContentType.YOUTUBE
        assert request.target_language == "fr"  # Default
        assert request.summary_length == SummaryLength.MEDIUM  # Default

    def test_summary_response_creation(self):
        """Test SummaryResponse creation."""
        response = SummaryResponse(
            summary="Test summary",
            tokens_used=100,
            language="en",
            length=SummaryLength.BRIEF,
            processing_time=1.5
        )
        
        assert response.summary == "Test summary"
        assert response.tokens_used == 100
        assert response.cached is False  # Default
        assert response.created_at is not None

    def test_summary_response_post_init(self):
        """Test SummaryResponse post-initialization."""
        response = SummaryResponse(
            summary="Test",
            tokens_used=50,
            language="fr",
            length=SummaryLength.MEDIUM,
            processing_time=1.0
        )
        
        # created_at should be set automatically
        assert isinstance(response.created_at, datetime)

class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_summarize_content_function(self):
        """Test the convenience summarize_content function."""
        with patch('summarizers.deepseek.get_summarizer') as mock_get_summarizer:
            mock_summarizer = AsyncMock()
            mock_response = SummaryResponse(
                summary="Test summary",
                tokens_used=100,
                language="fr",
                length=SummaryLength.MEDIUM,
                processing_time=1.5
            )
            mock_summarizer.summarize.return_value = mock_response
            mock_get_summarizer.return_value = mock_summarizer
            
            result = await summarize_content(
                content="test content",
                content_type="youtube",
                target_language="fr"
            )
            
            assert result == mock_response
            mock_summarizer.summarize.assert_called_once()
            
            # Check the request was created correctly
            call_args = mock_summarizer.summarize.call_args[0][0]
            assert call_args.content == "test content"
            assert call_args.content_type == ContentType.YOUTUBE

    def test_get_summarizer_singleton(self):
        """Test that get_summarizer returns singleton instance."""
        with patch('summarizers.deepseek.DeepSeekSummarizer') as mock_class:
            with patch('summarizers.deepseek.get_database_manager'):
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                
                # First call should create instance
                result1 = get_summarizer()
                # Second call should return same instance
                result2 = get_summarizer()
                
                assert result1 == result2
                mock_class.assert_called_once()  # Constructor called only once

class TestEnums:
    """Test enum classes."""

    def test_summary_length_enum(self):
        """Test SummaryLength enum values."""
        assert SummaryLength.BRIEF.value == "brief"
        assert SummaryLength.MEDIUM.value == "medium"
        assert SummaryLength.DETAILED.value == "detailed"

    def test_content_type_enum(self):
        """Test ContentType enum values."""
        assert ContentType.YOUTUBE.value == "youtube"
        assert ContentType.WEB.value == "web"
        assert ContentType.UNIVERSAL.value == "universal"

# Test configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__])