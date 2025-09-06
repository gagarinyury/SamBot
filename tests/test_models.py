"""
Tests for data models in models/ directory.
Clean, comprehensive test suite following best practices.
"""

import pytest
from datetime import datetime
from typing import List, Dict

from models.video import (
    YouTubeVideoInfo, 
    TranscriptInfo, 
    ExtractionRequest, 
    ExtractionResponse,
    TranscriptType,
    ExtractionStatus
)
from models.user import UserSettings, SummaryStates, DEFAULT_USER_SETTINGS


class TestYouTubeVideoInfo:
    """Test YouTubeVideoInfo model."""
    
    def test_video_info_creation(self):
        """Test basic video info creation."""
        video_info = YouTubeVideoInfo(
            video_id="dQw4w9WgXcQ",
            title="Test Video Title",
            channel="Test Channel",
            duration=180,  # 3 minutes
            view_count=1000000,
            publish_date=datetime(2024, 1, 15),
            description="Test video description"
        )
        
        assert video_info.video_id == "dQw4w9WgXcQ"
        assert video_info.title == "Test Video Title"
        assert video_info.channel == "Test Channel"
        assert video_info.duration == 180
        assert video_info.view_count == 1000000
        assert video_info.description == "Test video description"
        assert video_info.language is None  # Optional field
    
    def test_video_info_with_language(self):
        """Test video info with language field."""
        video_info = YouTubeVideoInfo(
            video_id="test123",
            title="Title",
            channel="Channel",
            duration=60,
            view_count=100,
            publish_date=datetime.now(),
            description="Description",
            language="en"
        )
        
        assert video_info.language == "en"
    
    def test_video_info_empty_description(self):
        """Test video info with empty description."""
        video_info = YouTubeVideoInfo(
            video_id="test123",
            title="Title",
            channel="Channel", 
            duration=60,
            view_count=100,
            publish_date=datetime.now(),
            description=""
        )
        
        assert video_info.description == ""


class TestTranscriptInfo:
    """Test TranscriptInfo model."""
    
    def test_transcript_info_creation(self):
        """Test transcript info creation."""
        transcript = TranscriptInfo(
            language="Russian",
            language_code="ru",
            is_generated=False,
            is_translatable=True
        )
        
        assert transcript.language == "Russian"
        assert transcript.language_code == "ru"
        assert transcript.is_generated is False
        assert transcript.is_translatable is True
    
    def test_auto_generated_transcript(self):
        """Test auto-generated transcript info."""
        transcript = TranscriptInfo(
            language="English",
            language_code="en",
            is_generated=True,
            is_translatable=False
        )
        
        assert transcript.is_generated is True
        assert transcript.is_translatable is False


class TestExtractionRequest:
    """Test ExtractionRequest model."""
    
    def test_request_with_defaults(self):
        """Test request creation with default values."""
        request = ExtractionRequest(url="https://youtube.com/watch?v=test123")
        
        assert request.url == "https://youtube.com/watch?v=test123"
        assert request.preferred_languages == ['fr', 'en', 'ru']
        assert request.allow_auto_generated is True
        assert request.user_id is None
    
    def test_request_with_custom_values(self):
        """Test request with custom values."""
        request = ExtractionRequest(
            url="https://youtube.com/watch?v=test123",
            preferred_languages=['en', 'de'],
            allow_auto_generated=False,
            user_id=12345
        )
        
        assert request.preferred_languages == ['en', 'de']
        assert request.allow_auto_generated is False
        assert request.user_id == 12345
    
    def test_request_post_init(self):
        """Test post_init behavior."""
        # Test with None preferred_languages
        request = ExtractionRequest(
            url="test_url",
            preferred_languages=None
        )
        
        assert request.preferred_languages == ['fr', 'en', 'ru']


class TestExtractionResponse:
    """Test ExtractionResponse model."""
    
    def test_successful_response(self):
        """Test successful extraction response."""
        video_info = YouTubeVideoInfo(
            video_id="test123",
            title="Test",
            channel="Channel",
            duration=60,
            view_count=100,
            publish_date=datetime.now(),
            description="Desc"
        )
        
        transcript_info = TranscriptInfo(
            language="Russian",
            language_code="ru", 
            is_generated=False,
            is_translatable=True
        )
        
        segments = [
            {"start": 0, "text": "Hello world"},
            {"start": 5, "text": "This is a test"}
        ]
        
        response = ExtractionResponse(
            status=ExtractionStatus.SUCCESS,
            content="Extracted content",
            video_info=video_info,
            transcript_info=transcript_info,
            transcript_segments=segments,
            processing_time=1.5,
            detected_language="ru"
        )
        
        assert response.status == ExtractionStatus.SUCCESS
        assert response.content == "Extracted content"
        assert response.video_info == video_info
        assert response.transcript_info == transcript_info
        assert response.transcript_segments == segments
        assert response.processing_time == 1.5
        assert response.error_message == ""
        assert response.detected_language == "ru"
    
    def test_error_response(self):
        """Test error extraction response."""
        response = ExtractionResponse(
            status=ExtractionStatus.ERROR,
            content="",
            error_message="Video not found"
        )
        
        assert response.status == ExtractionStatus.ERROR
        assert response.content == ""
        assert response.video_info is None
        assert response.transcript_info is None
        assert response.transcript_segments is None
        assert response.processing_time == 0.0
        assert response.error_message == "Video not found"


class TestEnums:
    """Test enum classes."""
    
    def test_transcript_type_enum(self):
        """Test TranscriptType enum."""
        assert TranscriptType.MANUAL.value == "manual"
        assert TranscriptType.AUTO_GENERATED.value == "auto_generated"
        assert TranscriptType.UNAVAILABLE.value == "unavailable"
    
    def test_extraction_status_enum(self):
        """Test ExtractionStatus enum."""
        assert ExtractionStatus.SUCCESS.value == "success"
        assert ExtractionStatus.NO_TRANSCRIPT.value == "no_transcript"
        assert ExtractionStatus.ERROR.value == "error"
        assert ExtractionStatus.VIDEO_NOT_FOUND.value == "video_not_found"
        assert ExtractionStatus.VIDEO_UNAVAILABLE.value == "video_unavailable"
        assert ExtractionStatus.VIDEO_TOO_LONG.value == "video_too_long"


class TestUserSettings:
    """Test UserSettings model."""
    
    def test_user_settings_creation(self):
        """Test user settings creation with defaults."""
        settings = UserSettings(user_id=12345)
        
        assert settings.user_id == 12345
        assert settings.language == "ru"
        assert settings.summary_type == "detailed"
        assert settings.created_at is None
        assert settings.updated_at is None
    
    def test_user_settings_custom_values(self):
        """Test user settings with custom values."""
        settings = UserSettings(
            user_id=67890,
            language="en",
            summary_type="brief",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z"
        )
        
        assert settings.user_id == 67890
        assert settings.language == "en"
        assert settings.summary_type == "brief"
        assert settings.created_at == "2024-01-01T00:00:00Z"
        assert settings.updated_at == "2024-01-02T00:00:00Z"
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        settings = UserSettings(
            user_id=12345,
            language="fr",
            summary_type="brief"
        )
        
        result = settings.to_dict()
        expected = {
            'user_id': 12345,
            'language': 'fr',
            'summary_type': 'brief',
            'created_at': None,
            'updated_at': None
        }
        
        assert result == expected
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'user_id': 12345,
            'language': 'en',
            'summary_type': 'detailed',
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-02T00:00:00Z'
        }
        
        settings = UserSettings.from_dict(data)
        
        assert settings.user_id == 12345
        assert settings.language == 'en'
        assert settings.summary_type == 'detailed'
        assert settings.created_at == '2024-01-01T00:00:00Z'
        assert settings.updated_at == '2024-01-02T00:00:00Z'


class TestConstants:
    """Test module constants."""
    
    def test_default_user_settings(self):
        """Test default user settings constant."""
        assert DEFAULT_USER_SETTINGS["language"] == "ru"
        assert DEFAULT_USER_SETTINGS["summary_type"] == "detailed"
    
    def test_summary_states_exists(self):
        """Test that SummaryStates class exists and has waiting_for_url state."""
        # Just verify the class exists and can be imported
        assert SummaryStates is not None
        assert hasattr(SummaryStates, 'waiting_for_url')


# Test fixtures for reuse
@pytest.fixture
def sample_video_info():
    """Fixture providing sample video info."""
    return YouTubeVideoInfo(
        video_id="sample123",
        title="Sample Video",
        channel="Sample Channel",
        duration=300,
        view_count=50000,
        publish_date=datetime(2024, 3, 15),
        description="Sample description",
        language="en"
    )


@pytest.fixture
def sample_transcript_segments():
    """Fixture providing sample transcript segments."""
    return [
        {"start": 0, "text": "Welcome to this video"},
        {"start": 3, "text": "Today we will discuss"},
        {"start": 7, "text": "Important topics"}
    ]


class TestIntegration:
    """Integration tests combining multiple models."""
    
    def test_complete_extraction_workflow(self, sample_video_info, sample_transcript_segments):
        """Test complete extraction workflow with all models."""
        # Create request
        request = ExtractionRequest(
            url="https://youtube.com/watch?v=sample123",
            user_id=12345
        )
        
        # Create transcript info
        transcript_info = TranscriptInfo(
            language="English",
            language_code="en",
            is_generated=False,
            is_translatable=True
        )
        
        # Create successful response
        response = ExtractionResponse(
            status=ExtractionStatus.SUCCESS,
            content="Full transcript content",
            video_info=sample_video_info,
            transcript_info=transcript_info,
            transcript_segments=sample_transcript_segments,
            processing_time=2.1,
            detected_language="en"
        )
        
        # Verify everything works together
        assert response.status == ExtractionStatus.SUCCESS
        assert response.video_info.video_id == "sample123"
        assert response.transcript_info.language_code == "en"
        assert len(response.transcript_segments) == 3
        assert response.transcript_segments[0]["text"] == "Welcome to this video"