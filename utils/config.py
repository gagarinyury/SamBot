"""
Configuration utilities for SamBot.
Clean implementation of environment-based configuration.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class BotConfig:
    """Main bot configuration class."""
    telegram_token: str
    deepseek_api_key: str
    perplexity_api_key: Optional[str] = None
    environment: str = "development"
    log_level: str = "INFO"
    max_text_length: int = 50000
    secret_key: str = "default_secret"
    
    # YouTube settings
    max_video_duration: int = 7200  # 2 hours
    preferred_languages: List[str] = None
    allow_auto_generated: bool = True
    
    # User settings
    default_language: str = "ru"
    default_summary_type: str = "detailed"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not self.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        
        # Set default preferred languages if not provided
        if self.preferred_languages is None:
            self.preferred_languages = ['ru', 'en', 'fr']
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"
    
    def get_logging_level(self) -> int:
        """Get logging level as integer."""
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return levels.get(self.log_level.upper(), logging.INFO)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "telegram_token": "***HIDDEN***",  # Never expose tokens
            "deepseek_api_key": "***HIDDEN***",
            "perplexity_api_key": "***HIDDEN***" if self.perplexity_api_key else None,
            "environment": self.environment,
            "log_level": self.log_level,
            "max_text_length": self.max_text_length,
            "max_video_duration": self.max_video_duration,
            "preferred_languages": self.preferred_languages,
            "allow_auto_generated": self.allow_auto_generated,
            "default_language": self.default_language,
            "default_summary_type": self.default_summary_type,
        }


def load_config() -> BotConfig:
    """
    Load configuration from environment variables.
    
    Returns:
        BotConfig: Configured bot instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    try:
        config = BotConfig(
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
            environment=os.getenv("ENVIRONMENT", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_text_length=int(os.getenv("MAX_TEXT_LENGTH", "50000")),
            secret_key=os.getenv("SECRET_KEY", "default_secret"),
            max_video_duration=int(os.getenv("MAX_VIDEO_DURATION", "7200")),
            allow_auto_generated=os.getenv("ALLOW_AUTO_GENERATED", "true").lower() == "true",
            default_language=os.getenv("DEFAULT_LANGUAGE", "ru"),
            default_summary_type=os.getenv("DEFAULT_SUMMARY_TYPE", "detailed"),
        )
        
        # Handle preferred languages from env
        lang_env = os.getenv("PREFERRED_LANGUAGES", "ru,en,fr")
        if lang_env:
            config.preferred_languages = [lang.strip() for lang in lang_env.split(",")]
        
        return config
        
    except ValueError as e:
        raise ValueError(f"Configuration error: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load configuration: {e}")


def get_config() -> BotConfig:
    """
    Get singleton configuration instance.
    
    Returns:
        BotConfig: Global configuration instance
    """
    if not hasattr(get_config, "_config"):
        get_config._config = load_config()
    return get_config._config


# Constants for the application
class Constants:
    """Application constants."""
    
    # Message limits
    TELEGRAM_MESSAGE_LIMIT = 4096
    TELEGRAM_CAPTION_LIMIT = 1024
    
    # Video limits
    MIN_VIDEO_DURATION = 10  # seconds
    MAX_VIDEO_DURATION_DEFAULT = 7200  # 2 hours
    
    # Text processing
    TRANSCRIPT_PREVIEW_SEGMENTS = 20
    DESCRIPTION_TRUNCATE_LENGTH = 500
    TITLE_TRUNCATE_LENGTH = 500
    
    # Supported languages
    SUPPORTED_LANGUAGES = {
        "ru": "Русский",
        "en": "English", 
        "fr": "Français"
    }
    
    # Summary types
    SUMMARY_TYPES = {
        "brief": "Краткое",
        "detailed": "Подробное"
    }
    
    # Default error messages
    ERROR_MESSAGES = {
        "video_not_found": "Видео не найдено или недоступно",
        "no_transcript": "Субтитры для видео недоступны",
        "video_too_long": "Видео слишком длинное для обработки",
        "extraction_failed": "Ошибка при извлечении контента",
        "ai_error": "Ошибка при генерации резюме",
        "invalid_url": "Неверная ссылка на YouTube",
    }