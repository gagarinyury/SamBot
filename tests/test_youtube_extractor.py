"""
Unit tests for YouTube Extractor.
Tests core functionality without making actual API calls.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Import the module we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors.youtube import (
    YouTubeExtractor,
    ExtractionRequest,
    ExtractionResponse,
    YouTubeVideoInfo,
    TranscriptInfo,
    ExtractionStatus,
    TranscriptType,
    YouTubeExtractorError,
    VideoUnavailableError,
    TranscriptUnavailableError,
    get_youtube_extractor,
    extract_youtube_content
)

class TestYouTubeExtractor:
    """Test cases for YouTubeExtractor class."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.youtube.preferred_languages = ['fr', 'en', 'ru']
        config.youtube.allow_auto_generated = True
        config.youtube.max_video_duration = 7200
        return config

    @pytest.fixture
    def mock_db(self):
        """Mock database manager."""
        db = AsyncMock()
        db.log_event.return_value = None
        db.log_error.return_value = None
        return db

    @pytest.fixture
    def extractor(self, mock_config, mock_db):
        """Create extractor instance with mocked dependencies."""
        with patch('extractors.youtube.get_config', return_value=mock_config):
            return YouTubeExtractor(mock_db)

    def test_init(self, extractor):
        """Test extractor initialization."""
        assert extractor.db is not None
        assert extractor.config is not None
        assert extractor.youtube_config is not None
        assert extractor.stats['total_extractions'] == 0
        assert len(extractor.youtube_patterns) == 4

    def test_validate_youtube_url_valid_urls(self, extractor):
        """Test YouTube URL validation with valid URLs."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/v/dQw4w9WgXcQ",
            "youtube.com/watch?v=dQw4w9WgXcQ",  # Without protocol
        ]
        
        for url in valid_urls:
            assert extractor.validate_youtube_url(url), f"URL should be valid: {url}"

    def test_validate_youtube_url_invalid_urls(self, extractor):
        """Test YouTube URL validation with invalid URLs."""
        invalid_urls = [
            "",
            None,
            "not_a_url",
            "https://vimeo.com/123456",
            "https://www.facebook.com/watch",
            "https://youtube.com",  # No video ID
            "https://www.youtube.com/watch?v=invalid_id_too_long",
        ]
        
        for url in invalid_urls:
            assert not extractor.validate_youtube_url(url), f"URL should be invalid: {url}"

    def test_extract_video_id(self, extractor):
        """Test video ID extraction from URLs."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("invalid_url", None),
        ]
        
        for url, expected_id in test_cases:
            result = extractor.extract_video_id(url)
            assert result == expected_id, f"Expected {expected_id} for {url}, got {result}"

    def test_detect_content_language(self, extractor):
        """Test content language detection."""
        # Test French content
        french_content = "Bonjour, comment allez-vous? Ceci est un texte en français pour tester la détection de langue."
        
        # Test English content
        english_content = "Hello, how are you? This is an English text to test language detection capabilities."
        
        # Test short content (should return None)
        short_content = "Hi"
        
        with patch('extractors.youtube.detect') as mock_detect:
            mock_detect.return_value = 'fr'
            result = extractor.detect_content_language(french_content)
            assert result == 'fr'
            
            mock_detect.return_value = 'en'
            result = extractor.detect_content_language(english_content)
            assert result == 'en'
            
            # Short content should not be detected
            result = extractor.detect_content_language(short_content)
            assert result is None

    def test_select_best_transcript_manual_preferred(self, extractor):
        """Test transcript selection preferring manual transcripts."""
        transcripts = [
            TranscriptInfo("English", "en", is_generated=True, is_translatable=True),
            TranscriptInfo("Français", "fr", is_generated=False, is_translatable=True),
            TranscriptInfo("Русский", "ru", is_generated=True, is_translatable=True),
        ]
        
        # Should prefer French manual transcript
        result = extractor.select_best_transcript(transcripts, ['fr', 'en'], True)
        assert result is not None
        assert result.language_code == 'fr'
        assert not result.is_generated

    def test_select_best_transcript_fallback_to_auto(self, extractor):
        """Test transcript selection falling back to auto-generated."""
        transcripts = [
            TranscriptInfo("English", "en", is_generated=True, is_translatable=True),
            TranscriptInfo("Русский", "ru", is_generated=True, is_translatable=True),
        ]
        
        # Should fallback to English auto-generated
        result = extractor.select_best_transcript(transcripts, ['fr', 'en'], True)
        assert result is not None
        assert result.language_code == 'en'
        assert result.is_generated

    def test_select_best_transcript_no_auto_allowed(self, extractor):
        """Test transcript selection when auto-generated not allowed."""
        transcripts = [
            TranscriptInfo("English", "en", is_generated=True, is_translatable=True),
            TranscriptInfo("Русский", "ru", is_generated=True, is_translatable=True),
        ]
        
        # Should return None as no manual transcripts available
        result = extractor.select_best_transcript(transcripts, ['fr', 'en'], False)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_video_info_success(self, extractor):
        """Test successful video info retrieval."""
        mock_youtube = MagicMock()
        mock_youtube.title = "Test Video"
        mock_youtube.author = "Test Channel"
        mock_youtube.length = 300
        mock_youtube.views = 1000
        mock_youtube.publish_date = datetime(2025, 1, 1)
        mock_youtube.description = "Test description"
        mock_youtube.thumbnail_url = "https://example.com/thumb.jpg"
        
        with patch('extractors.youtube.YouTube', return_value=mock_youtube):
            result = await extractor.get_video_info("dQw4w9WgXcQ")
            
        assert result is not None
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.title == "Test Video"
        assert result.channel == "Test Channel"
        assert result.duration == 300

    @pytest.mark.asyncio
    async def test_get_video_info_duration_exceeded(self, extractor):
        """Test video info with duration exceeding limit."""
        mock_youtube = MagicMock()
        mock_youtube.title = "Long Video"
        mock_youtube.author = "Test Channel"
        mock_youtube.length = 10000  # Exceeds 7200 limit
        mock_youtube.views = 1000
        mock_youtube.publish_date = datetime(2025, 1, 1)
        mock_youtube.description = "Test description"
        mock_youtube.thumbnail_url = "https://example.com/thumb.jpg"
        
        with patch('extractors.youtube.YouTube', return_value=mock_youtube):
            result = await extractor.get_video_info("dQw4w9WgXcQ")
            
        assert result is not None
        assert result.duration == 10000

    @pytest.mark.asyncio
    async def test_get_video_info_unavailable(self, extractor):
        """Test video info for unavailable video."""
        from pytube.exceptions import VideoUnavailable as PytubeVideoUnavailable
        
        with patch('extractors.youtube.YouTube') as mock_youtube:
            mock_youtube.side_effect = PytubeVideoUnavailable(video_id="invalid_id")
            with pytest.raises(VideoUnavailableError):
                await extractor.get_video_info("invalid_id")

    def test_get_available_transcripts_success(self, extractor):
        """Test getting available transcripts."""
        mock_transcript_list = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.language = "English"
        mock_transcript.language_code = "en"
        mock_transcript.is_generated = False
        mock_transcript.translation_languages = ['fr', 'ru']
        mock_transcript_list.__iter__.return_value = [mock_transcript]
        
        with patch.object(extractor.transcript_api, 'list_transcripts', return_value=mock_transcript_list):
            result = extractor.get_available_transcripts("dQw4w9WgXcQ")
            
        assert len(result) == 1
        assert result[0].language == "English"
        assert result[0].language_code == "en"
        assert not result[0].is_generated

    def test_get_available_transcripts_not_found(self, extractor):
        """Test getting transcripts when none available."""
        from youtube_transcript_api import NoTranscriptFound
        
        with patch.object(extractor.transcript_api, 'list_transcripts',
                         side_effect=NoTranscriptFound("video_id", [], [])):
            result = extractor.get_available_transcripts("invalid_id")
            
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_transcript_success(self, extractor):
        """Test successful transcript extraction."""
        mock_transcript_data = [
            {'text': 'Hello world', 'start': 0, 'duration': 2},
            {'text': 'This is a test', 'start': 2, 'duration': 3},
            {'text': '[Music]', 'start': 5, 'duration': 1},  # Should be cleaned
        ]
        
        transcript_info = TranscriptInfo("English", "en", False, True)
        
        # Mock the transcript list and transcript object
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = mock_transcript_data
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.return_value = mock_transcript
        
        with patch.object(extractor.transcript_api, 'list_transcripts', return_value=mock_transcript_list):
            result = await extractor.extract_transcript("dQw4w9WgXcQ", transcript_info)
            
        assert "Hello world This is a test" in result
        assert "[Music]" not in result  # Should be cleaned

    @pytest.mark.asyncio
    async def test_extract_transcript_failure(self, extractor):
        """Test transcript extraction failure."""
        transcript_info = TranscriptInfo("English", "en", False, True)
        
        with patch.object(extractor.transcript_api, 'list_transcripts', side_effect=Exception("API Error")):
            with pytest.raises(TranscriptUnavailableError):
                await extractor.extract_transcript("invalid_id", transcript_info)

    @pytest.mark.asyncio
    async def test_extract_invalid_url(self, extractor):
        """Test extraction with invalid URL."""
        request = ExtractionRequest(url="https://invalid-url.com")
        result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.INVALID_URL
        assert result.content == ""
        assert "Invalid YouTube URL" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_success_flow(self, extractor):
        """Test complete successful extraction flow."""
        # Mock video info
        video_info = YouTubeVideoInfo(
            video_id="dQw4w9WgXcQ",
            title="Test Video",
            channel="Test Channel",
            duration=300,
            view_count=1000,
            publish_date=datetime.utcnow(),
            description="Test"
        )
        
        # Mock transcript info
        transcript_info = TranscriptInfo("English", "en", False, True)
        transcripts = [transcript_info]
        
        request = ExtractionRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        with patch.object(extractor, 'get_video_info', return_value=video_info):
            with patch.object(extractor, 'get_available_transcripts', return_value=transcripts):
                with patch.object(extractor, 'extract_transcript', return_value="Test transcript content"):
                    with patch.object(extractor, 'detect_content_language', return_value='en'):
                        result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.SUCCESS
        assert result.content == "Test transcript content"
        assert result.video_info.title == "Test Video"
        assert result.transcript_info.language_code == "en"
        assert result.detected_language == 'en'

    @pytest.mark.asyncio
    async def test_extract_no_transcripts(self, extractor):
        """Test extraction when no transcripts available."""
        video_info = YouTubeVideoInfo(
            video_id="dQw4w9WgXcQ",
            title="Test Video",
            channel="Test Channel",
            duration=300,
            view_count=1000,
            publish_date=datetime.utcnow(),
            description="Test"
        )
        
        request = ExtractionRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        with patch.object(extractor, 'get_video_info', return_value=video_info):
            with patch.object(extractor, 'get_available_transcripts', return_value=[]):
                result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.NO_TRANSCRIPT
        assert "No transcripts available" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_video_unavailable(self, extractor):
        """Test extraction when video is unavailable."""
        request = ExtractionRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        with patch.object(extractor, 'get_video_info', return_value=None):
            result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.VIDEO_UNAVAILABLE
        assert "unavailable or private" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_duration_exceeded(self, extractor):
        """Test extraction when video duration exceeds limit."""
        video_info = YouTubeVideoInfo(
            video_id="dQw4w9WgXcQ",
            title="Long Video",
            channel="Test Channel", 
            duration=10000,  # Exceeds limit
            view_count=1000,
            publish_date=datetime.utcnow(),
            description="Test"
        )
        
        request = ExtractionRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        with patch.object(extractor, 'get_video_info', return_value=video_info):
            result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.DURATION_EXCEEDED
        assert "exceeds limit" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_rejects_long_video(self, extractor):
        """Test that the extract method rejects a video that is too long."""
        # This video is over 2 hours long, so it should be rejected.
        long_video_url = "https://www.youtube.com/watch?v=8hly31xKli0"
        request = ExtractionRequest(url=long_video_url)

        # Mock the pytube response to control the duration
        mock_youtube = MagicMock()
        mock_youtube.title = "Long Video"
        mock_youtube.author = "Test Channel"
        mock_youtube.length = 8000  # > 7200, so it should be rejected
        mock_youtube.views = 1000
        mock_youtube.publish_date = datetime.utcnow()
        mock_youtube.description = "A long video"
        mock_youtube.thumbnail_url = "https://example.com/thumb.jpg"
        mock_youtube.check_availability.return_value = None


        with patch('extractors.youtube.YouTube', return_value=mock_youtube) as mock_pytube:
            result = await extractor.extract(request)
            mock_pytube.assert_called_once_with(f"https://www.youtube.com/watch?v=8hly31xKli0")


        assert result.status == ExtractionStatus.DURATION_EXCEEDED
        assert "exceeds limit" in result.error_message

    def test_get_stats(self, extractor):
        """Test statistics retrieval."""
        # Add some mock data
        extractor.stats['total_extractions'] = 10
        extractor.stats['successful_extractions'] = 8
        extractor.stats['failed_extractions'] = 2
        extractor.stats['auto_generated_used'] = 3
        
        stats = extractor.get_stats()
        
        assert stats['success_rate'] == 80.0  # 8/10 * 100
        assert stats['auto_generated_rate'] == 37.5  # 3/8 * 100
        assert stats['total_extractions'] == 10

class TestDataClasses:
    """Test data classes used in YouTube extraction."""

    def test_extraction_request_creation(self):
        """Test ExtractionRequest creation with defaults."""
        request = ExtractionRequest(url="https://youtube.com/watch?v=test")
        
        assert request.url == "https://youtube.com/watch?v=test"
        assert request.preferred_languages == ['fr', 'en', 'ru']  # Default
        assert request.allow_auto_generated is True  # Default

    def test_extraction_response_creation(self):
        """Test ExtractionResponse creation."""
        response = ExtractionResponse(
            status=ExtractionStatus.SUCCESS,
            content="Test content"
        )
        
        assert response.status == ExtractionStatus.SUCCESS
        assert response.content == "Test content"
        assert response.processing_time == 0.0  # Default
        assert response.created_at is not None

    def test_youtube_video_info_creation(self):
        """Test YouTubeVideoInfo creation."""
        video_info = YouTubeVideoInfo(
            video_id="test123",
            title="Test Video",
            channel="Test Channel",
            duration=300,
            view_count=1000,
            publish_date=datetime.utcnow(),
            description="Test description"
        )
        
        assert video_info.video_id == "test123"
        assert video_info.title == "Test Video"
        assert video_info.duration == 300

class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_extract_youtube_content_function(self):
        """Test the convenience extract_youtube_content function."""
        with patch('extractors.youtube.get_youtube_extractor') as mock_get_extractor:
            mock_extractor = AsyncMock()
            mock_response = ExtractionResponse(
                status=ExtractionStatus.SUCCESS,
                content="Test content"
            )
            mock_extractor.extract.return_value = mock_response
            mock_get_extractor.return_value = mock_extractor
            
            result = await extract_youtube_content(
                url="https://youtube.com/watch?v=test",
                preferred_languages=['fr', 'en']
            )
            
            assert result == mock_response
            mock_extractor.extract.assert_called_once()
            
            # Check the request was created correctly
            call_args = mock_extractor.extract.call_args[0][0]
            assert call_args.url == "https://youtube.com/watch?v=test"
            assert call_args.preferred_languages == ['fr', 'en']

    def test_get_youtube_extractor_singleton(self):
        """Test that get_youtube_extractor returns singleton instance."""
        with patch('extractors.youtube.YouTubeExtractor') as mock_class:
            with patch('extractors.youtube.get_database_manager'):
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                
                # First call should create instance
                result1 = get_youtube_extractor()
                # Second call should return same instance
                result2 = get_youtube_extractor()
                
                assert result1 == result2
                mock_class.assert_called_once()  # Constructor called only once

class TestEnums:
    """Test enum classes."""

    def test_extraction_status_enum(self):
        """Test ExtractionStatus enum values."""
        assert ExtractionStatus.SUCCESS.value == "success"
        assert ExtractionStatus.NO_TRANSCRIPT.value == "no_transcript"
        assert ExtractionStatus.VIDEO_UNAVAILABLE.value == "video_unavailable"
        assert ExtractionStatus.INVALID_URL.value == "invalid_url"

    def test_transcript_type_enum(self):
        """Test TranscriptType enum values."""
        assert TranscriptType.MANUAL.value == "manual"
        assert TranscriptType.AUTO_GENERATED.value == "auto_generated"
        assert TranscriptType.UNAVAILABLE.value == "unavailable"

# Test configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__])