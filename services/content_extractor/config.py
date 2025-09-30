"""Configuration settings for Content Extractor service."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql://sambot:password@postgres:5432/sambot_v2"

    # Audio storage
    AUDIO_STORAGE_PATH: str = "/app/audio_storage"
    AUTO_CLEANUP_DAYS: int = 7

    # yt-dlp settings
    MAX_AUDIO_QUALITY: int = 192  # kbps
    SOCKET_TIMEOUT: int = 30
    PREFERRED_AUDIO_FORMAT: str = "mp3"
    COOKIES_FILE: str = ""  # Path to cookies file (for Instagram, etc.)

    # Chunking
    DEFAULT_CHUNK_SIZE: int = 500  # tokens
    DEFAULT_CHUNK_OVERLAP: int = 50  # tokens

    # Whisper settings
    WHISPER_MODEL: str = "base"  # tiny, base, small, medium, large
    WHISPER_DEVICE: str = "cpu"  # cpu or cuda
    WHISPER_LANGUAGE: Optional[str] = None  # None for auto-detect, or "ru", "en", etc.

    # Service
    SERVICE_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()