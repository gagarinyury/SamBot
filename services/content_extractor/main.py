"""FastAPI application for Content Extractor service."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from config import settings
from database import db
from extractor import extractor
from models import (
    ExtractionRequest,
    ExtractionResponse,
    ErrorResponse
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info("service_starting", port=settings.SERVICE_PORT)
    await db.connect()
    logger.info("service_started")

    yield

    # Shutdown
    logger.info("service_stopping")
    await db.disconnect()
    logger.info("service_stopped")


app = FastAPI(
    title="Content Extractor Service",
    description="Universal content extraction with yt-dlp (YouTube + other platforms)",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        if db.pool:
            await db.pool.fetchval("SELECT 1")
            db_status = "connected"
        else:
            db_status = "disconnected"

        return {
            "status": "healthy",
            "service": "content_extractor",
            "version": "2.0.0",
            "database": db_status
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.post("/extract", response_model=ExtractionResponse)
async def extract_content(request: ExtractionRequest):
    """
    Extract content from URL.

    Automatically detects best strategy:
    - YouTube with transcript → metadata + transcript + chunks
    - YouTube without transcript → metadata + audio file
    - Other platforms → metadata + audio file

    Caching:
    - Checks database before extraction
    - Returns cached result if URL already processed
    """
    try:
        logger.info(
            "extraction_requested",
            url=request.url[:50],
            user_id=request.user_id
        )

        result = await extractor.extract(
            url=request.url,
            user_id=request.user_id,
            language=request.language
        )

        return ExtractionResponse(**result)

    except ValueError as e:
        logger.error("extraction_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error("extraction_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )


@app.get("/content/{content_id}")
async def get_content(content_id: int):
    """
    Get extracted content by ID.

    Returns:
        Content metadata, transcript/audio info, and chunks
    """
    try:
        query = """
            SELECT
                oc.id,
                oc.original_url,
                oc.content_type,
                oc.metadata,
                oc.raw_content,
                oc.audio_file_path,
                oc.extraction_method,
                oc.created_at,
                (
                    SELECT json_agg(
                        json_build_object(
                            'index', chunk_index,
                            'text', chunk_text,
                            'start_timestamp', start_timestamp,
                            'end_timestamp', end_timestamp,
                            'tokens', chunk_tokens
                        ) ORDER BY chunk_index
                    )
                    FROM content_chunks
                    WHERE content_id = oc.id
                ) as chunks
            FROM original_content oc
            WHERE oc.id = $1
        """

        row = await db.pool.fetchrow(query, content_id)

        if not row:
            raise HTTPException(status_code=404, detail="Content not found")

        return {
            "content_id": row['id'],
            "url": row['original_url'],
            "platform": row['content_type'],
            "metadata": row['metadata'],
            "has_transcript": bool(row['raw_content']),
            "has_audio": bool(row['audio_file_path']),
            "transcript_length": len(row['raw_content']) if row['raw_content'] else None,
            "audio_file": row['audio_file_path'],
            "extraction_method": row['extraction_method'],
            "created_at": row['created_at'].isoformat(),
            "chunks": row['chunks'] or []
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("content_fetch_failed", error=str(e), content_id=content_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get extraction statistics."""
    try:
        query = """
            SELECT
                COUNT(*) as total_content,
                COUNT(*) FILTER (WHERE raw_content IS NOT NULL) as with_transcript,
                COUNT(*) FILTER (WHERE audio_file_path IS NOT NULL) as with_audio,
                COUNT(DISTINCT content_type) as platforms,
                (SELECT COUNT(*) FROM content_chunks) as total_chunks
            FROM original_content
        """

        row = await db.pool.fetchrow(query)

        return {
            "total_content": row['total_content'],
            "with_transcript": row['with_transcript'],
            "with_audio": row['with_audio'],
            "platforms": row['platforms'],
            "total_chunks": row['total_chunks']
        }

    except Exception as e:
        logger.error("stats_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.SERVICE_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False
    )