"""
SamBot Configuration Module
Manages all configuration settings loaded from environment variables.
"""
import os
import logging
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class AIConfig:
    """AI/Summarization configuration."""
    deepseek_api_key: str
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    max_text_length: int = 50000
    
    def __post_init__(self):
        if not self.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")

@dataclass 
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str
    webhook_url: Optional[str] = None
    webhook_port: int = 8443
    
    def __post_init__(self):
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

@dataclass
class YouTubeConfig:
    """YouTube extraction configuration."""
    preferred_languages: List[str]
    allow_auto_generated: bool = True
    max_video_duration: int = 7200  # 2 hours in seconds
    
    def __post_init__(self):
        if isinstance(self.preferred_languages, str):
            self.preferred_languages = [lang.strip() for lang in self.preferred_languages.split(',')]

@dataclass
class WebConfig:
    """Web parsing configuration."""
    user_agent: str
    request_timeout: int = 30
    connect_timeout: int = 10
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None

@dataclass
class SecurityConfig:
    """Security and rate limiting configuration."""
    secret_key: str
    rate_limit_per_minute: int = 10
    rate_limit_per_hour: int = 50 
    rate_limit_per_day: int = 200
    
    def __post_init__(self):
        if not self.secret_key:
            raise ValueError("SECRET_KEY is required for security")

@dataclass
class MonitoringConfig:
    """Monitoring and analytics configuration."""
    sentry_dsn: Optional[str] = None
    ga_tracking_id: Optional[str] = None

class Config:
    """
    Main configuration class that loads and validates all settings.
    """
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
        
        # Initialize configuration sections
        self.ai = AIConfig(
            deepseek_api_key=os.getenv('DEEPSEEK_API_KEY', ''),
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
            max_text_length=int(os.getenv('MAX_TEXT_LENGTH', '50000'))
        )
        
        self.telegram = TelegramConfig(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            webhook_url=os.getenv('TELEGRAM_WEBHOOK_URL'),
            webhook_port=int(os.getenv('TELEGRAM_WEBHOOK_PORT', '8443'))
        )
        
        self.youtube = YouTubeConfig(
            preferred_languages=os.getenv('YOUTUBE_PREFERRED_LANGUAGES', 'en,ru,es,fr,de'),
            allow_auto_generated=os.getenv('YOUTUBE_ALLOW_AUTO_GENERATED', 'true').lower() == 'true',
            max_video_duration=int(os.getenv('MAX_VIDEO_DURATION', '7200'))
        )
        
        self.web = WebConfig(
            user_agent=os.getenv('USER_AGENT', 'SamBot/1.0 (+https://github.com/gagarinyury/SamBot)'),
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '30')),
            connect_timeout=int(os.getenv('CONNECT_TIMEOUT', '10')),
            http_proxy=os.getenv('HTTP_PROXY'),
            https_proxy=os.getenv('HTTPS_PROXY')
        )
        
        self.security = SecurityConfig(
            secret_key=os.getenv('SECRET_KEY', ''),
            rate_limit_per_minute=int(os.getenv('RATE_LIMIT_PER_MINUTE', '10')),
            rate_limit_per_hour=int(os.getenv('RATE_LIMIT_PER_HOUR', '50')),
            rate_limit_per_day=int(os.getenv('RATE_LIMIT_PER_DAY', '200'))
        )
        
        self.monitoring = MonitoringConfig(
            sentry_dsn=os.getenv('SENTRY_DSN'),
            ga_tracking_id=os.getenv('GA_TRACKING_ID')
        )
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == 'development'
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == 'production'
    
    def setup_logging(self) -> None:
        """Configure logging based on environment and log level."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        if self.is_development:
            # More verbose logging in development
            logging.basicConfig(
                level=self.log_level,
                format=f'%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            # Cleaner logging in production
            logging.basicConfig(
                level=self.log_level,
                format=log_format,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def validate(self) -> None:
        """
        Validate all configuration settings.
        Raises ValueError if any required settings are missing.
        """
        errors = []
        
        # Validate required API keys
        if not self.ai.deepseek_api_key:
            errors.append("DEEPSEEK_API_KEY is required")
        
        if not self.telegram.bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")
            
        if not self.security.secret_key:
            errors.append("SECRET_KEY is required")
        
        # Validate numeric ranges
        if self.ai.max_text_length <= 0:
            errors.append("MAX_TEXT_LENGTH must be positive")
            
        if self.youtube.max_video_duration <= 0:
            errors.append("MAX_VIDEO_DURATION must be positive")
        
        if self.web.request_timeout <= 0:
            errors.append("REQUEST_TIMEOUT must be positive")
            
        # Validate rate limits
        if self.security.rate_limit_per_minute <= 0:
            errors.append("RATE_LIMIT_PER_MINUTE must be positive")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def __str__(self) -> str:
        """String representation of config (without sensitive data)."""
        return (
            f"Config(environment={self.environment}, "
            f"log_level={logging.getLevelName(self.log_level)}, "
            f"ai_configured={bool(self.ai.deepseek_api_key)}, "
            f"telegram_configured={bool(self.telegram.bot_token)})"
        )

# Global configuration instance
config = Config()

# Convenience function to get config
def get_config() -> Config:
    """Get the global configuration instance."""
    return config

if __name__ == "__main__":
    # Test configuration loading
    try:
        config.validate()
        config.setup_logging()
        print("✅ Configuration loaded successfully!")
        print(config)
    except Exception as e:
        print(f"❌ Configuration error: {e}")