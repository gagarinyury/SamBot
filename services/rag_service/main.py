"""RAG Service API - Semantic search and Q&A over video transcripts."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional
import structlog

from config import settings
from database import db
from ollama_client import ollama
from rag_engine import rag_engine

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
    logger.info("rag_service_starting")
    await db.connect()

    # Check Ollama availability
    if await ollama.check_health():
        logger.info(
            "ollama_connected",
            url=settings.OLLAMA_URL,
            embedding_model=settings.EMBEDDING_MODEL,
            llm_model=settings.LLM_MODEL
        )
    else:
        logger.warning("ollama_not_available", url=settings.OLLAMA_URL)

    yield

    # Shutdown
    logger.info("rag_service_stopping")
    await db.disconnect()
    await ollama.close()


app = FastAPI(
    title="RAG Service",
    description="Semantic search and Q&A over video transcripts using embeddings",
    version="1.0.0",
    lifespan=lifespan
)


class EmbedRequest(BaseModel):
    """Request to generate embedding."""
    content_id: int


class SearchRequest(BaseModel):
    """Request to search content."""
    query: str
    top_k: Optional[int] = None
    min_similarity: Optional[float] = None
    content_id: Optional[int] = None


class AskRequest(BaseModel):
    """Request to ask question."""
    question: str
    top_k: Optional[int] = None
    min_similarity: Optional[float] = None
    content_id: Optional[int] = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    ollama_healthy = await ollama.check_health()

    return {
        "status": "healthy" if ollama_healthy else "degraded",
        "ollama": "connected" if ollama_healthy else "unavailable",
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm_model": settings.LLM_MODEL,
        "embedding_dim": settings.EMBEDDING_DIMENSION
    }


@app.post("/embed")
async def embed_content(request: EmbedRequest):
    """
    Generate and save embedding for content.

    Process:
    1. Fetch content from database
    2. Generate embedding using Ollama
    3. Save embedding to database
    """
    content_id = request.content_id

    logger.info("embedding_requested", content_id=content_id)

    try:
        success = await rag_engine.generate_and_save_embedding(content_id)

        if not success:
            raise HTTPException(status_code=404, detail="Content not found or has no transcript")

        return {
            "content_id": content_id,
            "status": "success",
            "model": settings.EMBEDDING_MODEL,
            "dimension": settings.EMBEDDING_DIMENSION
        }

    except Exception as e:
        logger.error("embedding_failed", content_id=content_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search_content(request: SearchRequest):
    """
    Semantic search for similar content.

    Process:
    1. Generate query embedding
    2. Search database using vector similarity
    3. Return top-k results with similarity scores
    """
    try:
        results = await rag_engine.search(
            query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            content_id=request.content_id
        )

        return {
            "query": request.query,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error("search_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask")
async def ask_question(request: AskRequest):
    """
    Ask question using RAG.

    Process:
    1. Search for relevant content
    2. Build context from search results
    3. Generate answer using LLM with context
    4. Return answer with sources
    """
    try:
        result = await rag_engine.ask(
            question=request.question,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            content_id=request.content_id
        )

        return result

    except Exception as e:
        logger.error("ask_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
