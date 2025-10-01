"""Configuration for summarizer service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # AI Provider: "ollama" or "deepseek"
    AI_PROVIDER: str = "deepseek"

    # Ollama settings (if AI_PROVIDER=ollama)
    OLLAMA_URL: str = "http://host.docker.internal:11434"
    MODEL_NAME: str = "qwen2.5:7b-instruct-q4_K_M"

    # DeepSeek settings (if AI_PROVIDER=deepseek)
    DEEPSEEK_API_KEY: str = ""

    # Database
    DATABASE_URL: str

    # Summarization settings
    MAX_SUMMARY_LENGTH: int = 4096  # tokens (DeepSeek supports up to 4096)
    TEMPERATURE: float = 0.3  # Lower = more focused

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
