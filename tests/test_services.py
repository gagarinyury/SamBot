"""
Tests for services in services/ directory.
Comprehensive test suite for YouTube and Summarizer services.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, List

from services.youtube_service import YouTubeService
from services.summarizer_service import SummarizerService
from models.video import (
    YouTubeVideoInfo, 
    ExtractionResponse, 
    ExtractionStatus,
    TranscriptInfo
)
from models.user import UserSettings
from utils.config import Constants


class TestYouTubeService:
    """Test YouTube service functionality."""
    
    @pytest.fixture
    def youtube_service(self):
        """Fixture providing YouTube service instance."""
        return YouTubeService()
    
    @pytest.fixture
    def sample_video_info(self):
        """Fixture providing sample video info."""
        return YouTubeVideoInfo(
            video_id="test123",
            title="Test Video Title",
            channel="Test Channel",
            duration=300,  # 5 minutes
            view_count=100000,
            publish_date=datetime(2024, 3, 15),
            description="Test video description",
            language="en"
        )
    
    @pytest.fixture
    def sample_transcript_segments(self):
        """Fixture providing sample transcript segments."""
        return [
            {"start": 0, "text": "Hello and welcome to this video"},
            {"start": 5, "text": "Today we will discuss important topics"},
            {"start": 12, "text": "Let's start with the basics"},
            {"start": 18, "text": "This is very important to understand"}
        ]
    
    def test_youtube_service_initialization(self, youtube_service):
        """Test YouTube service initializes correctly."""
        assert youtube_service is not None
        assert youtube_service.config is not None
        assert youtube_service.formatter is not None
        assert youtube_service.transcript_formatter is not None
        assert youtube_service.message_formatter is not None
    
    def test_is_valid_youtube_url(self, youtube_service):
        """Test YouTube URL validation."""
        valid_urls = [
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        
        invalid_urls = [
            "",
            "https://google.com",
            "not a url",
            "https://vimeo.com/123456789",
            None
        ]
        
        for url in valid_urls:
            assert youtube_service._is_valid_youtube_url(url), f"URL should be valid: {url}"
        
        for url in invalid_urls:
            assert not youtube_service._is_valid_youtube_url(url), f"URL should be invalid: {url}"
    
    def test_validate_video_duration(self, youtube_service, sample_video_info):
        """Test video duration validation."""
        # Valid duration
        assert youtube_service.validate_video_duration(sample_video_info)
        
        # Too short
        short_video = sample_video_info
        short_video.duration = 5  # Less than MIN_VIDEO_DURATION (10)
        assert not youtube_service.validate_video_duration(short_video)
        
        # Too long (assuming max duration is 7200 seconds by default)
        long_video = sample_video_info
        long_video.duration = 10000  # More than max duration
        assert not youtube_service.validate_video_duration(long_video)
    
    def test_map_extraction_error(self, youtube_service):
        """Test error message mapping to status codes."""
        test_cases = [
            ("Video not found", ExtractionStatus.VIDEO_NOT_FOUND),
            ("Video unavailable", ExtractionStatus.VIDEO_NOT_FOUND),
            ("No transcript available", ExtractionStatus.NO_TRANSCRIPT),
            ("Subtitle not found", ExtractionStatus.NO_TRANSCRIPT),
            ("Video too long", ExtractionStatus.VIDEO_TOO_LONG),
            ("Duration exceeded", ExtractionStatus.VIDEO_TOO_LONG),
            ("Unknown error", ExtractionStatus.ERROR),
            ("", ExtractionStatus.ERROR)
        ]
        
        for error_msg, expected_status in test_cases:
            result = youtube_service._map_extraction_error(error_msg)
            assert result == expected_status, f"Error '{error_msg}' should map to {expected_status}"
    
    def test_format_video_message_success(self, youtube_service, sample_video_info, sample_transcript_segments):
        """Test successful video message formatting."""
        extraction_result = ExtractionResponse(
            status=ExtractionStatus.SUCCESS,
            content="Test content",
            video_info=sample_video_info,
            transcript_segments=sample_transcript_segments
        )
        
        message = youtube_service.format_video_message(extraction_result)
        
        assert "🎥 <b>Название:</b>" in message
        assert "Test Video Title" in message
        assert "👤 <b>Канал:</b>" in message
        assert "Test Channel" in message
        assert "📅 <b>Дата:</b>" in message
        assert "⏱️ <b>Длительность:</b>" in message
        assert "👁️ <b>Просмотры:</b>" in message
        assert "📖 <b>Описание</b>" in message
    
    def test_format_video_message_error(self, youtube_service):
        """Test error message formatting."""
        extraction_result = ExtractionResponse(
            status=ExtractionStatus.ERROR,
            content="",
            error_message="Test error message"
        )
        
        message = youtube_service.format_video_message(extraction_result)
        
        assert "❌" in message
        assert "error" in message.lower()
    
    def test_create_expandable_transcript(self, youtube_service, sample_video_info, sample_transcript_segments):
        """Test expandable transcript creation."""
        result = youtube_service.create_expandable_transcript(
            sample_video_info, 
            sample_transcript_segments
        )
        
        assert "<blockquote expandable>" in result
        assert "</blockquote>" in result
        assert "📝 НАЧАЛО ВИДЕО:" in result
        assert "[00:00] Hello and welcome" in result
        assert sample_video_info.description in result
    
    def test_create_expandable_transcript_no_segments(self, youtube_service, sample_video_info):
        """Test expandable transcript with no segments."""
        result = youtube_service.create_expandable_transcript(sample_video_info, None)
        assert result == ""
        
        result = youtube_service.create_expandable_transcript(sample_video_info, [])
        assert result == ""
    
    def test_should_use_fallback_message(self, youtube_service):
        """Test fallback message decision logic."""
        # Short message - no fallback needed
        assert not youtube_service.should_use_fallback_message(1000)
        
        # Long message - fallback needed
        assert youtube_service.should_use_fallback_message(Constants.TELEGRAM_MESSAGE_LIMIT + 100)
    
    def test_create_fallback_message(self, youtube_service, sample_video_info):
        """Test fallback message creation."""
        fallback = youtube_service.create_fallback_message(sample_video_info, max_description_length=100)
        
        assert "🎥 <b>Название:</b>" in fallback
        assert "👤 <b>Канал:</b>" in fallback
        assert "📅 <b>Дата:</b>" in fallback
        assert "⏱️ <b>Длительность:</b>" in fallback
        assert "👁️ <b>Просмотры:</b>" in fallback
        assert "📖 <b>Описание:</b>" in fallback
        
        # Should be shorter than original
        assert len(fallback) < 2000
    
    def test_get_progress_message(self, youtube_service):
        """Test progress message formatting."""
        message = youtube_service.get_progress_message("Extracting video info", 1, 3)
        
        assert "⏳" in message
        assert "Extracting video info" in message
        assert "1/3" in message
    
    @pytest.mark.asyncio
    async def test_extract_video_info_invalid_url(self, youtube_service):
        """Test extraction with invalid URL."""
        result = await youtube_service.extract_video_info("not_a_youtube_url")
        
        assert result.status == ExtractionStatus.ERROR
        assert "Invalid YouTube URL" in result.error_message
        assert result.video_info is None
    
    @pytest.mark.asyncio
    @patch('services.youtube_service.extract_youtube_content')
    async def test_extract_video_info_success(self, mock_extract, youtube_service, sample_video_info, sample_transcript_segments):
        """Test successful video extraction."""
        # Mock the extractor response
        mock_response = Mock()
        mock_response.content = "Test transcript content"
        mock_response.video_info = sample_video_info
        mock_response.transcript_info = TranscriptInfo("English", "en", False, True)
        mock_response.transcript_segments = sample_transcript_segments
        mock_response.detected_language = "en"
        mock_response.error_message = ""
        
        mock_extract.return_value = mock_response
        
        result = await youtube_service.extract_video_info("https://youtube.com/watch?v=test123")
        
        assert result.status == ExtractionStatus.SUCCESS
        assert result.content == "Test transcript content"
        assert result.video_info == sample_video_info
        assert result.transcript_segments == sample_transcript_segments
        assert result.processing_time > 0


class TestSummarizerService:
    """Test Summarizer service functionality."""
    
    @pytest.fixture
    def summarizer_service(self):
        """Fixture providing Summarizer service instance."""
        return SummarizerService()
    
    @pytest.fixture
    def sample_user_settings(self):
        """Fixture providing sample user settings."""
        return UserSettings(
            user_id=12345,
            language="ru",
            summary_type="detailed"
        )
    
    @pytest.fixture
    def sample_video_info(self):
        """Fixture providing sample video info."""
        return YouTubeVideoInfo(
            video_id="test123",
            title="Test Video Title",
            channel="Test Channel",
            duration=300,
            view_count=100000,
            publish_date=datetime(2024, 3, 15),
            description="Test description"
        )
    
    def test_summarizer_service_initialization(self, summarizer_service):
        """Test Summarizer service initializes correctly."""
        assert summarizer_service is not None
        assert summarizer_service.config is not None
        assert summarizer_service.message_formatter is not None
        assert summarizer_service.languages is not None
        assert summarizer_service.summary_types is not None
    
    def test_get_supported_languages(self, summarizer_service):
        """Test supported languages retrieval."""
        languages = summarizer_service.get_supported_languages()
        
        assert isinstance(languages, dict)
        assert "ru" in languages
        assert "en" in languages
        assert "fr" in languages
        
        # Check structure
        for lang_code, lang_info in languages.items():
            assert "name" in lang_info
            assert "flag" in lang_info
            assert "emoji" in lang_info
    
    def test_get_summary_types(self, summarizer_service):
        """Test summary types retrieval."""
        summary_types = summarizer_service.get_summary_types()
        
        assert isinstance(summary_types, dict)
        assert "brief" in summary_types
        assert "detailed" in summary_types
        
        # Check structure
        for type_code, type_info in summary_types.items():
            assert "name" in type_info
            assert "desc" in type_info
            assert "emoji" in type_info
    
    def test_validate_content_length(self, summarizer_service):
        """Test content length validation."""
        # Too short
        assert not summarizer_service.validate_content_length("")
        assert not summarizer_service.validate_content_length("short")
        
        # Good length
        good_content = "This is a sufficiently long piece of content that should be acceptable for summarization. " * 5
        assert summarizer_service.validate_content_length(good_content)
        
        # Too long (assuming max length from config)
        very_long_content = "x" * 100000
        with patch.object(summarizer_service.config, 'max_text_length', 50000):
            assert not summarizer_service.validate_content_length(very_long_content)
    
    def test_estimate_processing_time(self, summarizer_service):
        """Test processing time estimation."""
        # Short content
        short_time = summarizer_service.estimate_processing_time(500)
        assert short_time >= 3  # Minimum time
        
        # Medium content
        medium_time = summarizer_service.estimate_processing_time(5000)
        assert medium_time >= 3
        assert medium_time <= 30
        
        # Long content
        long_time = summarizer_service.estimate_processing_time(50000)
        assert long_time <= 30  # Maximum cap
    
    def test_should_suggest_brief_summary(self, summarizer_service):
        """Test brief summary suggestion logic."""
        # Short content - suggest brief
        assert summarizer_service.should_suggest_brief_summary(3000)
        
        # Long content - don't suggest brief
        assert not summarizer_service.should_suggest_brief_summary(10000)
    
    def test_get_progress_message(self, summarizer_service, sample_user_settings):
        """Test progress message formatting."""
        message = summarizer_service.get_progress_message(sample_user_settings)
        
        assert "🤖" in message
        assert "резюме" in message.lower()
        assert "🇷🇺" in message  # Russian flag for ru language
        assert "📖" in message  # Detailed summary emoji
    
    def test_get_progress_message_default_settings(self, summarizer_service):
        """Test progress message with default settings."""
        message = summarizer_service.get_progress_message()
        
        assert "🤖" in message
        assert "резюме" in message.lower()
    
    def test_format_summary_message_error(self, summarizer_service):
        """Test error message formatting."""
        error_result = {
            "success": False,
            "error": "Test error message",
            "error_type": "ai_error"
        }
        
        message = summarizer_service.format_summary_message(error_result)
        
        assert "❌" in message
        assert "error" in message.lower()
    
    def test_format_summary_message_success(self, summarizer_service, sample_video_info):
        """Test successful summary message formatting."""
        success_result = {
            "success": True,
            "summary": "This is a test summary of the video content.",
            "language_info": {"name": "русский", "flag": "🇷🇺"},
            "summary_info": {"name": "Подробное", "emoji": "📖"},
            "processing_time": 2.5,
            "tokens_used": 150,
            "cache_hit": False
        }
        
        message = summarizer_service.format_summary_message(success_result, sample_video_info)
        
        assert "🤖 <b>ИИ Резюме</b>" in message
        assert "This is a test summary" in message
        assert "🇷🇺" in message
        assert "📖" in message
        assert "2.5с" in message
        assert "150 токенов" in message
    
    def test_format_summary_message_with_cache_hit(self, summarizer_service):
        """Test summary message formatting with cache hit."""
        success_result = {
            "success": True,
            "summary": "Cached summary content.",
            "language_info": {"name": "english", "flag": "🇺🇸"},
            "summary_info": {"name": "Brief", "emoji": "⚡"},
            "processing_time": 0.1,
            "cache_hit": True,
            "tokens_used": 50
        }
        
        message = summarizer_service.format_summary_message(success_result)
        
        assert "💾 <i>Из кэша</i>" in message
        assert "50 токенов" in message
    
    @pytest.mark.asyncio
    @patch('services.summarizer_service.summarize_content')
    async def test_generate_summary_success(self, mock_summarize, summarizer_service, sample_user_settings):
        """Test successful summary generation."""
        # Mock the summarizer response
        mock_response = Mock()
        mock_response.summary = "Test AI summary content"
        mock_response.tokens_used = 100
        mock_response.model_used = "deepseek"
        mock_response.cache_hit = False
        
        mock_summarize.return_value = mock_response
        
        result = await summarizer_service.generate_summary(
            content="Long video transcript content here...",
            user_settings=sample_user_settings,
            user_id=12345
        )
        
        assert result["success"] is True
        assert result["summary"] == "Test AI summary content"
        assert result["tokens_used"] == 100
        assert result["model_used"] == "deepseek"
        assert result["cache_hit"] is False
        assert "language_info" in result
        assert "summary_info" in result
        assert result["processing_time"] > 0
    
    @pytest.mark.asyncio
    @patch('services.summarizer_service.summarize_content')
    async def test_generate_summary_content_too_long(self, mock_summarize, summarizer_service):
        """Test summary generation with content too long."""
        # Mock config to have small max length
        with patch.object(summarizer_service.config, 'max_text_length', 100):
            result = await summarizer_service.generate_summary(
                content="x" * 200,  # Exceeds max length
                user_id=12345
            )
        
        assert result["success"] is False
        assert result["error_type"] == "content_too_long"
        assert "too long" in result["error"]
    
    @pytest.mark.asyncio
    @patch('services.summarizer_service.summarize_content')
    async def test_generate_summary_ai_failure(self, mock_summarize, summarizer_service):
        """Test summary generation when AI fails."""
        # Mock AI failure
        mock_summarize.return_value = None
        
        result = await summarizer_service.generate_summary(
            content="Test content",
            user_id=12345
        )
        
        assert result["success"] is False
        assert result["error_type"] == "ai_error"
        assert "AI summary generation failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_summary_statistics(self, summarizer_service):
        """Test summary statistics retrieval."""
        stats = await summarizer_service.get_summary_statistics(12345)
        
        # Should return placeholder data for now
        assert isinstance(stats, dict)
        assert "total_summaries" in stats
        assert "total_tokens" in stats
        assert "favorite_language" in stats
        assert "favorite_summary_type" in stats


class TestServiceIntegration:
    """Integration tests for services working together."""
    
    @pytest.fixture
    def youtube_service(self):
        return YouTubeService()
    
    @pytest.fixture
    def summarizer_service(self):
        return SummarizerService()
    
    @pytest.fixture
    def sample_extraction_result(self):
        """Sample extraction result for integration tests."""
        video_info = YouTubeVideoInfo(
            video_id="integration123",
            title="Integration Test Video",
            channel="Test Channel",
            duration=600,  # 10 minutes
            view_count=250000,
            publish_date=datetime(2024, 3, 20),
            description="Integration test description"
        )
        
        transcript_segments = [
            {"start": 0, "text": "Welcome to our integration test"},
            {"start": 5, "text": "This video demonstrates service integration"},
            {"start": 12, "text": "We will test multiple components together"}
        ]
        
        return ExtractionResponse(
            status=ExtractionStatus.SUCCESS,
            content="Full transcript content for integration testing. This is a longer piece of content that would be suitable for AI summarization.",
            video_info=video_info,
            transcript_segments=transcript_segments,
            processing_time=1.5
        )
    
    def test_end_to_end_formatting(self, youtube_service, summarizer_service, sample_extraction_result):
        """Test end-to-end message formatting workflow."""
        # Format video message
        video_message = youtube_service.format_video_message(sample_extraction_result)
        
        assert "Integration Test Video" in video_message
        assert "📝 НАЧАЛО ВИДЕО:" in video_message
        assert "[00:00] Welcome to our integration test" in video_message
        
        # Format summary progress message
        user_settings = UserSettings(user_id=123, language="en", summary_type="brief")
        progress_message = summarizer_service.get_progress_message(user_settings)
        
        assert "🤖" in progress_message
        assert "🇺🇸" in progress_message  # English flag
        assert "⚡" in progress_message  # Brief summary emoji
    
    @pytest.mark.asyncio
    @patch('services.summarizer_service.summarize_content')
    async def test_full_video_processing_workflow(self, mock_summarize, youtube_service, summarizer_service, sample_extraction_result):
        """Test complete video processing workflow."""
        # Step 1: Format video info
        video_message = youtube_service.format_video_message(sample_extraction_result)
        assert len(video_message) > 0
        
        # Step 2: Generate summary
        mock_response = Mock()
        mock_response.summary = "Integration test summary generated successfully"
        mock_response.tokens_used = 75
        mock_summarize.return_value = mock_response
        
        user_settings = UserSettings(user_id=123, language="ru", summary_type="detailed")
        summary_result = await summarizer_service.generate_summary(
            content=sample_extraction_result.content,
            video_info=sample_extraction_result.video_info,
            user_settings=user_settings,
            user_id=123
        )
        
        assert summary_result["success"] is True
        
        # Step 3: Format summary message
        summary_message = summarizer_service.format_summary_message(
            summary_result, 
            sample_extraction_result.video_info
        )
        
        assert "Integration test summary" in summary_message
        assert "Integration Test Video" in summary_message
        assert "🇷🇺" in summary_message