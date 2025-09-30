"""
Content Extractor Service - FastAPI application.
Phase 1: YouTube extraction with chapter-based chunking.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict

from extractors.youtube import YouTubeExtractor, ExtractionStatus
from chunking.chapter_based import ChapterBasedChunker
from chunking.fixed_size import FixedSizeChunker
from database.connection import get_db_connection, close_db_connection
from database.repository import ContentRepository

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models
class ExtractionRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[int] = None
    language: str = "ru"


class ExtractionResponse(BaseModel):
    status: str
    content_id: Optional[int] = None
    platform: str = "youtube"
    extraction_method: str
    metadata: Dict
    chunking: Dict
    processing_time: float


class ContentResponse(BaseModel):
    content_id: int
    url: str
    platform: str
    content: str
    metadata: Dict
    chunks: List[Dict]


class HealthResponse(BaseModel):
    status: str
    database: str


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Content Extractor Service")
    try:
        await get_db_connection()
        logger.info("Database connected")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Content Extractor Service")
    await close_db_connection()


# FastAPI app
app = FastAPI(
    title="Content Extractor Service",
    description="YouTube content extraction with RAG chunking",
    version="2.0.0",
    lifespan=lifespan
)


@app.post("/extract", response_model=ExtractionResponse)
async def extract_content(request: ExtractionRequest):
    """
    Extract content from URL and store with chunks.

    Phase 1: YouTube only with chapter-based chunking.
    """
    try:
        # Initialize components
        extractor = YouTubeExtractor()
        db_pool = await get_db_connection()
        repo = ContentRepository(db_pool)

        # Extract content
        logger.info(f"Extracting content from: {request.url}")
        extraction_result = await extractor.extract(
            str(request.url),
            preferred_languages=[request.language, 'en']
        )

        if extraction_result.status != ExtractionStatus.SUCCESS:
            raise HTTPException(
                status_code=400,
                detail=f"Extraction failed: {extraction_result.error_message}"
            )

        video_info = extraction_result.video_info
        transcript_segments = extraction_result.transcript_segments

        # Prepare metadata
        metadata = {
            'title': video_info.title,
            'channel': video_info.channel,
            'duration': video_info.duration,
            'description': video_info.description,
            'language': extraction_result.detected_language,
            'chapters': video_info.chapters
        }

        # Store original content
        content_id = await repo.store_content(
            url=str(request.url),
            content=extraction_result.content,
            content_type='youtube',
            metadata=metadata,
            extraction_method='youtube_transcript_api',
            user_id=request.user_id
        )

        # Choose chunking strategy
        chunks_data = []
        strategy_name = "none"
        strategy_metadata = {}

        if video_info.chapters and video_info.chapters.get('has_chapters'):
            # Try chapter-based chunking
            chapter_chunker = ChapterBasedChunker()
            chapters = video_info.chapters.get('chapters', [])

            if chapter_chunker.should_use_chapters(chapters, video_info.duration):
                logger.info("Using chapter-based chunking")
                chunks = chapter_chunker.chunk_by_chapters(
                    extraction_result.content,
                    transcript_segments,
                    chapters,
                    video_info.duration
                )
                strategy_name = "chapter_based"
                strategy_metadata = {
                    'chapter_count': len(chapters),
                    'total_chunks': len(chunks)
                }
                chunks_data = [
                    {
                        'chunk_index': c.chunk_index,
                        'chunk_text': c.chunk_text,
                        'start_timestamp': c.start_timestamp,
                        'end_timestamp': c.end_timestamp,
                        'chunk_length': c.chunk_length,
                        'chunk_tokens': c.chunk_tokens,
                        'chapter_title': c.chapter_title
                    }
                    for c in chunks
                ]
            else:
                logger.info("Chapters not suitable, using fixed-size chunking")
                fixed_chunker = FixedSizeChunker(chunk_size=500)
                chunks = fixed_chunker.chunk(
                    extraction_result.content,
                    transcript_segments,
                    video_info.duration
                )
                strategy_name = fixed_chunker.get_strategy_name()
                strategy_metadata = {'total_chunks': len(chunks)}
                chunks_data = [
                    {
                        'chunk_index': c.chunk_index,
                        'chunk_text': c.chunk_text,
                        'start_timestamp': c.start_timestamp,
                        'end_timestamp': c.end_timestamp,
                        'chunk_length': c.chunk_length,
                        'chunk_tokens': c.chunk_tokens
                    }
                    for c in chunks
                ]
        else:
            # No chapters, use fixed-size
            logger.info("No chapters found, using fixed-size chunking")
            fixed_chunker = FixedSizeChunker(chunk_size=500)
            chunks = fixed_chunker.chunk(
                extraction_result.content,
                transcript_segments,
                video_info.duration
            )
            strategy_name = fixed_chunker.get_strategy_name()
            strategy_metadata = {'total_chunks': len(chunks)}
            chunks_data = [
                {
                    'chunk_index': c.chunk_index,
                    'chunk_text': c.chunk_text,
                    'start_timestamp': c.start_timestamp,
                    'end_timestamp': c.end_timestamp,
                    'chunk_length': c.chunk_length,
                    'chunk_tokens': c.chunk_tokens
                }
                for c in chunks
            ]

        # Store chunks
        if chunks_data:
            await repo.store_chunks(
                content_id,
                chunks_data,
                strategy_name,
                strategy_metadata
            )

        return ExtractionResponse(
            status="success",
            content_id=content_id,
            platform="youtube",
            extraction_method="youtube_transcript_api",
            metadata=metadata,
            chunking={
                'strategy': strategy_name,
                'total_chunks': len(chunks_data),
                **strategy_metadata
            },
            processing_time=extraction_result.processing_time
        )

    except Exception as e:
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/content/{content_id}", response_model=ContentResponse)
async def get_content(content_id: int):
    """Get content and chunks by ID."""
    try:
        db_pool = await get_db_connection()
        repo = ContentRepository(db_pool)

        content = await repo.get_content(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        chunks = await repo.get_chunks(content_id)

        return ContentResponse(
            content_id=content_id,
            url=content['original_url'],
            platform=content['content_type'],
            content=content['raw_content'],
            metadata=content['metadata'] if isinstance(content['metadata'], dict) else {},
            chunks=chunks
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        db_pool = await get_db_connection()
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return HealthResponse(status="healthy", database="connected")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(status="unhealthy", database="disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)