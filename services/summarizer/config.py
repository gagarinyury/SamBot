"""Configuration for summarizer service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Ollama settings
    OLLAMA_URL: str = "http://ollama:11434"
    MODEL_NAME: str = "qwen2.5:3b-instruct-q4_K_M"

    # Database
    DATABASE_URL: str

    # Summarization settings
    MAX_SUMMARY_LENGTH: int = 2000  # tokens (increased for structured notes)
    TEMPERATURE: float = 0.3  # Lower = more focused

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
