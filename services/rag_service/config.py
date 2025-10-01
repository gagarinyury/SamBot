"""Configuration for RAG service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Ollama settings
    OLLAMA_URL: str = "http://host.docker.internal:11434"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    LLM_MODEL: str = "qwen2.5:3b-instruct-q4_K_M"

    # Database
    DATABASE_URL: str

    # RAG settings
    EMBEDDING_DIMENSION: int = 768  # nomic-embed-text dimension
    TOP_K_RESULTS: int = 3  # Number of similar chunks to retrieve
    SIMILARITY_THRESHOLD: float = 0.7  # Minimum cosine similarity

    # Generation settings
    MAX_CONTEXT_LENGTH: int = 4000  # Max tokens for context
    TEMPERATURE: float = 0.3

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
