"""Worker configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Worker settings."""

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Services
    RAG_SERVICE_URL: str = "http://rag_service:8000"
    SUMMARIZER_URL: str = "http://summarizer:8000"

    # Worker
    WORKER_QUEUES: str = "embedding,summarization,default"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
