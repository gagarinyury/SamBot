"""
Unit tests for Web Extractor.
Tests core functionality without making actual HTTP requests.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Import the module we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors.web import (
    WebExtractor,
    ExtractionRequest,
    ExtractionResponse,
    WebArticleInfo,
    ExtractionMethod,
    ExtractionStatus,
    WebExtractorError,
    ContentUnavailableError,
    AccessDeniedError,
    get_web_extractor,
    extract_web_content
)

class TestWebExtractor:
    """Test cases for WebExtractor class."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.web.user_agent = "SamBot/1.0"
        config.web.request_timeout = 30
        config.web.connect_timeout = 10
        config.web.http_proxy = None
        config.web.https_proxy = None
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
        with patch('extractors.web.get_config', return_value=mock_config):
            return WebExtractor(mock_db)

    def test_init(self, extractor):
        """Test extractor initialization."""
        assert extractor.db is not None
        assert extractor.config is not None
        assert extractor.web_config is not None
        assert extractor.stats['total_extractions'] == 0
        assert len(extractor.blocked_extensions) > 0

    def test_validate_web_url_valid_urls(self, extractor):
        """Test web URL validation with valid URLs."""
        valid_urls = [
            "https://www.example.com/article",
            "http://news.example.org/story/123",
            "https://blog.example.net/post/title",
            "example.com/article",  # Without protocol
            "https://subdomain.example.com/path/to/article",
        ]
        
        for url in valid_urls:
            assert extractor.validate_web_url(url), f"URL should be valid: {url}"

    def test_validate_web_url_invalid_urls(self, extractor):
        """Test web URL validation with invalid URLs."""
        invalid_urls = [
            "",
            None,
            "not_a_url",
            "https://youtube.com/watch?v=123",  # Blocked video platform
            "https://youtu.be/123",
            "https://vimeo.com/123",
            "https://example.com/file.pdf",  # Blocked file extension
            "https://example.com/document.docx",
            "ftp://example.com/file",  # Wrong protocol
        ]
        
        for url in invalid_urls:
            assert not extractor.validate_web_url(url), f"URL should be invalid: {url}"

    def test_get_random_user_agent(self, extractor):
        """Test random user agent generation."""
        with patch.object(extractor.ua, 'random', return_value="Mozilla/5.0 Test"):
            user_agent = extractor.get_random_user_agent()
            assert user_agent == "Mozilla/5.0 Test"
        
        # Test fallback when ua.random fails
        with patch.object(extractor.ua, 'random', side_effect=Exception("UA Error")):
            user_agent = extractor.get_random_user_agent()
            assert user_agent == extractor.web_config.user_agent

    def test_detect_content_language(self, extractor):
        """Test content language detection."""
        # Test French content
        french_content = "Ceci est un article en français avec beaucoup de contenu pour tester la détection de langue. " * 3
        
        # Test English content  
        english_content = "This is an English article with plenty of content to test language detection capabilities. " * 3
        
        # Test short content (should return None)
        short_content = "Short"
        
        with patch('extractors.web.detect') as mock_detect:
            mock_detect.return_value = 'fr'
            result = extractor.detect_content_language(french_content)
            assert result == 'fr'
            
            mock_detect.return_value = 'en'
            result = extractor.detect_content_language(english_content)
            assert result == 'en'
            
            # Short content should not be detected
            result = extractor.detect_content_language(short_content)
            assert result is None

    @pytest.mark.asyncio
    async def test_check_robots_txt_allowed(self, extractor):
        """Test robots.txt check when access is allowed."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="User-agent: *\nDisallow: /admin")
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('extractors.web.aiohttp.ClientSession', return_value=mock_session):
            with patch('extractors.web.RobotFileParser') as mock_rp:
                mock_parser = MagicMock()
                mock_parser.can_fetch.return_value = True
                mock_rp.return_value = mock_parser
                
                result = await extractor.check_robots_txt("https://example.com/article")
                assert result is True

    @pytest.mark.asyncio
    async def test_check_robots_txt_blocked(self, extractor):
        """Test robots.txt check when access is blocked."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="User-agent: *\nDisallow: /")
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('extractors.web.aiohttp.ClientSession', return_value=mock_session):
            with patch('extractors.web.RobotFileParser') as mock_rp:
                mock_parser = MagicMock()
                mock_parser.can_fetch.return_value = False
                mock_rp.return_value = mock_parser
                
                result = await extractor.check_robots_txt("https://example.com/article")
                assert result is False

    @pytest.mark.asyncio
    async def test_check_robots_txt_no_file(self, extractor):
        """Test robots.txt check when file doesn't exist."""
        mock_response = MagicMock()
        mock_response.status = 404
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('extractors.web.aiohttp.ClientSession', return_value=mock_session):
            result = await extractor.check_robots_txt("https://example.com/article")
            assert result is True  # Should allow when no robots.txt

    @pytest.mark.asyncio
    async def test_extract_with_newspaper_success(self, extractor):
        """Test successful extraction with newspaper3k."""
        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.text = "This is the content of the test article. " * 10
        mock_article.authors = ["John Doe", "Jane Smith"]
        mock_article.publish_date = datetime(2025, 1, 1)
        mock_article.top_image = "https://example.com/image.jpg"
        mock_article.meta_description = "Test description"
        mock_article.meta_keywords = ["test", "article"]
        
        with patch('extractors.web.Article', return_value=mock_article):
            content, article_info = await extractor.extract_with_newspaper("https://example.com/article")
            
        assert "This is the content" in content
        assert article_info.title == "Test Article"
        assert article_info.authors == ["John Doe", "Jane Smith"]
        assert article_info.word_count > 0

    @pytest.mark.asyncio
    async def test_extract_with_newspaper_empty_content(self, extractor):
        """Test newspaper extraction with empty content."""
        mock_article = MagicMock()
        mock_article.title = "Empty Article"
        mock_article.text = ""  # Empty content
        
        with patch('extractors.web.Article', return_value=mock_article):
            with pytest.raises(ContentUnavailableError):
                await extractor.extract_with_newspaper("https://example.com/article")

    @pytest.mark.asyncio
    async def test_extract_with_newspaper_failure(self, extractor):
        """Test newspaper extraction failure."""
        mock_article = MagicMock()
        mock_article.download.side_effect = Exception("Download failed")
        
        with patch('extractors.web.Article', return_value=mock_article):
            with pytest.raises(ContentUnavailableError):
                await extractor.extract_with_newspaper("https://example.com/article")

    @pytest.mark.asyncio
    async def test_extract_with_beautifulsoup_success(self, extractor):
        """Test successful extraction with BeautifulSoup."""
        html_content = """
        <html>
        <head>
            <title>Test Article</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is the first paragraph of the test article.</p>
                <p>This is the second paragraph with more content.</p>
            </article>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=html_content)
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('extractors.web.Document') as mock_doc:
            mock_doc.return_value.summary.return_value = '<p>This is the first paragraph of the test article.</p><p>This is the second paragraph with more content.</p>'
            
            content, article_info = await extractor.extract_with_beautifulsoup("https://example.com/article", mock_session)
            
        assert "first paragraph" in content
        assert "second paragraph" in content
        assert article_info.title == "Test Article"
        assert article_info.meta_description == "Test description"

    @pytest.mark.asyncio
    async def test_extract_with_beautifulsoup_http_error(self, extractor):
        """Test BeautifulSoup extraction with HTTP error."""
        mock_response = MagicMock()
        mock_response.status = 404
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(AccessDeniedError):
            await extractor.extract_with_beautifulsoup("https://example.com/article", mock_session)

    @pytest.mark.asyncio
    async def test_extract_invalid_url(self, extractor):
        """Test extraction with invalid URL."""
        request = ExtractionRequest(url="https://youtube.com/watch?v=123")
        result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.INVALID_URL
        assert result.content == ""
        assert "Invalid or unsupported URL" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_robots_blocked(self, extractor):
        """Test extraction blocked by robots.txt."""
        request = ExtractionRequest(url="https://example.com/article", respect_robots=True)
        
        with patch.object(extractor, 'check_robots_txt', return_value=False):
            result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.ROBOTS_BLOCKED
        assert "robots.txt" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_success_newspaper(self, extractor):
        """Test successful extraction using newspaper."""
        request = ExtractionRequest(url="https://example.com/article", respect_robots=False)
        
        article_info = WebArticleInfo(
            url="https://example.com/article",
            title="Test Article",
            authors=["Author"],
            publish_date=datetime.utcnow(),
            top_image=None,
            meta_description="Description",
            meta_keywords=[],
            domain="example.com",
            word_count=50
        )
        
        with patch.object(extractor, 'extract_with_newspaper', return_value=("Test content for article", article_info)):
            with patch.object(extractor, 'detect_content_language', return_value='en'):
                result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.SUCCESS
        assert result.content == "Test content for article"
        assert result.extraction_method == ExtractionMethod.NEWSPAPER
        assert result.detected_language == 'en'

    @pytest.mark.asyncio
    async def test_extract_fallback_to_beautifulsoup(self, extractor):
        """Test fallback to BeautifulSoup when newspaper fails."""
        request = ExtractionRequest(url="https://example.com/article", respect_robots=False)
        
        article_info = WebArticleInfo(
            url="https://example.com/article",
            title="Test Article",
            authors=[],
            publish_date=None,
            top_image=None,
            meta_description=None,
            meta_keywords=[],
            domain="example.com",
            word_count=30
        )
        
        # Mock newspaper to fail
        with patch.object(extractor, 'extract_with_newspaper', side_effect=ContentUnavailableError("Newspaper failed")):
            # Mock BeautifulSoup to succeed
            with patch.object(extractor, 'extract_with_beautifulsoup', return_value=("Fallback content", article_info)):
                with patch.object(extractor, 'detect_content_language', return_value='en'):
                    result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.SUCCESS
        assert result.content == "Fallback content"
        assert result.extraction_method == ExtractionMethod.BEAUTIFULSOUP

    @pytest.mark.asyncio
    async def test_extract_content_too_long(self, extractor):
        """Test extraction with content exceeding length limit."""
        request = ExtractionRequest(url="https://example.com/article", max_content_length=50, respect_robots=False)
        
        long_content = "This is a very long article content. " * 10  # > 50 chars
        article_info = WebArticleInfo(
            url="https://example.com/article",
            title="Long Article",
            authors=[],
            publish_date=None,
            top_image=None,
            meta_description=None,
            meta_keywords=[],
            domain="example.com",
            word_count=100
        )
        
        with patch.object(extractor, 'extract_with_newspaper', return_value=(long_content, article_info)):
            with patch.object(extractor, 'detect_content_language', return_value='en'):
                result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.SUCCESS
        assert len(result.content) == 50  # Truncated

    @pytest.mark.asyncio
    async def test_extract_no_content(self, extractor):
        """Test extraction when no content available."""
        request = ExtractionRequest(url="https://example.com/article", respect_robots=False)
        
        with patch.object(extractor, 'extract_with_newspaper', side_effect=ContentUnavailableError("No content")):
            with patch.object(extractor, 'extract_with_beautifulsoup', side_effect=ContentUnavailableError("No content")):
                result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.NO_CONTENT
        assert "No content" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_timeout(self, extractor):
        """Test extraction timeout."""
        request = ExtractionRequest(url="https://example.com/article", respect_robots=False)
        
        with patch.object(extractor, 'extract_with_newspaper', side_effect=asyncio.TimeoutError("Timeout")):
            result = await extractor.extract(request)
        
        assert result.status == ExtractionStatus.TIMEOUT
        assert "timeout" in result.error_message.lower()

    def test_get_stats(self, extractor):
        """Test statistics retrieval."""
        # Add some mock data
        extractor.stats['total_extractions'] = 20
        extractor.stats['successful_extractions'] = 15
        extractor.stats['failed_extractions'] = 5
        extractor.stats['newspaper_used'] = 10
        extractor.stats['beautifulsoup_used'] = 5
        
        stats = extractor.get_stats()
        
        assert stats['success_rate'] == 75.0  # 15/20 * 100
        assert stats['newspaper_rate'] == 66.67  # 10/15 * 100 (rounded)
        assert stats['beautifulsoup_rate'] == 33.33  # 5/15 * 100 (rounded)

class TestDataClasses:
    """Test data classes used in web extraction."""

    def test_extraction_request_creation(self):
        """Test ExtractionRequest creation with defaults."""
        request = ExtractionRequest(url="https://example.com/article")
        
        assert request.url == "https://example.com/article"
        assert request.preferred_languages == ['fr', 'en', 'ru']  # Default
        assert request.max_content_length == 100000  # Default
        assert request.follow_redirects is True  # Default

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

    def test_web_article_info_creation(self):
        """Test WebArticleInfo creation."""
        article_info = WebArticleInfo(
            url="https://example.com/article",
            title="Test Article",
            authors=["Author 1"],
            publish_date=datetime.utcnow(),
            top_image="https://example.com/image.jpg",
            meta_description="Description",
            meta_keywords=["test"],
            domain="example.com",
            word_count=100
        )
        
        assert article_info.url == "https://example.com/article"
        assert article_info.title == "Test Article"
        assert article_info.word_count == 100

class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_extract_web_content_function(self):
        """Test the convenience extract_web_content function."""
        with patch('extractors.web.get_web_extractor') as mock_get_extractor:
            mock_extractor = AsyncMock()
            mock_response = ExtractionResponse(
                status=ExtractionStatus.SUCCESS,
                content="Test content"
            )
            mock_extractor.extract.return_value = mock_response
            mock_get_extractor.return_value = mock_extractor
            
            result = await extract_web_content(
                url="https://example.com/article",
                preferred_languages=['fr', 'en']
            )
            
            assert result == mock_response
            mock_extractor.extract.assert_called_once()
            
            # Check the request was created correctly
            call_args = mock_extractor.extract.call_args[0][0]
            assert call_args.url == "https://example.com/article"
            assert call_args.preferred_languages == ['fr', 'en']

    def test_get_web_extractor_singleton(self):
        """Test that get_web_extractor returns singleton instance."""
        with patch('extractors.web.WebExtractor') as mock_class:
            with patch('extractors.web.get_database_manager'):
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                
                # First call should create instance
                result1 = get_web_extractor()
                # Second call should return same instance
                result2 = get_web_extractor()
                
                assert result1 == result2
                mock_class.assert_called_once()  # Constructor called only once

class TestEnums:
    """Test enum classes."""

    def test_extraction_status_enum(self):
        """Test ExtractionStatus enum values."""
        assert ExtractionStatus.SUCCESS.value == "success"
        assert ExtractionStatus.NO_CONTENT.value == "no_content"
        assert ExtractionStatus.INVALID_URL.value == "invalid_url"
        assert ExtractionStatus.ACCESS_DENIED.value == "access_denied"

    def test_extraction_method_enum(self):
        """Test ExtractionMethod enum values."""
        assert ExtractionMethod.NEWSPAPER.value == "newspaper"
        assert ExtractionMethod.BEAUTIFULSOUP.value == "beautifulsoup"
        assert ExtractionMethod.READABILITY.value == "readability"
        assert ExtractionMethod.COMBINED.value == "combined"

# Test configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__])