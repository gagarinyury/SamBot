"""Summarizer service API."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
import structlog

from config import settings
from database import db
from ollama_client import ollama
from summarizer import summarizer

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("summarizer_service_starting")
    await db.connect()

    # Check Ollama availability
    if await ollama.check_health():
        logger.info("ollama_connected", url=settings.OLLAMA_URL, model=settings.MODEL_NAME)
    else:
        logger.warning("ollama_not_available", url=settings.OLLAMA_URL)

    yield

    # Shutdown
    logger.info("summarizer_service_stopping")
    await db.disconnect()
    await ollama.close()


app = FastAPI(
    title="Summarizer Service",
    description="AI-powered content summarization using Ollama",
    version="1.0.0",
    lifespan=lifespan
)


class SummarizeRequest(BaseModel):
    """Request to summarize content."""
    content_id: int


class SummarizeResponse(BaseModel):
    """Summarization response."""
    content_id: int
    summary: str
    summary_length: int


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    ollama_healthy = await ollama.check_health()

    return {
        "status": "healthy" if ollama_healthy else "degraded",
        "ollama": "connected" if ollama_healthy else "unavailable",
        "model": settings.MODEL_NAME
    }


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize_content(request: SummarizeRequest):
    """
    Summarize content by ID.

    Process:
    1. Fetch content from database
    2. Check if summary already exists
    3. Generate summary using Ollama
    4. Save to database
    5. Return result
    """
    content_id = request.content_id

    # Get content from database
    content = await db.get_content(content_id)

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check if already summarized
    if content.get('summary'):
        logger.info("summary_already_exists", content_id=content_id)
        return SummarizeResponse(
            content_id=content_id,
            summary=content['summary'],
            summary_length=len(content['summary'])
        )

    # Check if transcript available
    if not content.get('raw_content'):
        raise HTTPException(
            status_code=400,
            detail="No transcript available for this content"
        )

    # Generate summary
    logger.info("summarizing_content", content_id=content_id)

    summary = await summarizer.summarize(
        transcript=content['raw_content'],
        metadata=content.get('metadata')
    )

    # Save to database
    await db.save_summary(content_id, summary)

    return SummarizeResponse(
        content_id=content_id,
        summary=summary,
        summary_length=len(summary)
    )


@app.get("/summary/{content_id}")
async def get_summary(content_id: int):
    """Get existing summary for content."""
    content = await db.get_content(content_id)

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if not content.get('summary'):
        raise HTTPException(
            status_code=404,
            detail="Summary not found. Use POST /summarize to generate one."
        )

    return {
        "content_id": content_id,
        "summary": content['summary'],
        "metadata": content.get('metadata')
    }
