"""Background tasks for processing."""

import httpx
import structlog
from typing import Dict, Any

from config import settings

logger = structlog.get_logger()


def generate_embedding(content_id: int) -> Dict[str, Any]:
    """
    Background task: Generate embedding for content.

    Args:
        content_id: ID of content to embed

    Returns:
        Result dict
    """
    logger.info("task_generate_embedding_start", content_id=content_id)

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{settings.RAG_SERVICE_URL}/embed",
                json={"content_id": content_id}
            )

            response.raise_for_status()
            result = response.json()

            logger.info("task_generate_embedding_success", content_id=content_id)
            return {"status": "success", "result": result}

    except Exception as e:
        logger.error("task_generate_embedding_failed", content_id=content_id, error=str(e))
        return {"status": "error", "error": str(e)}


def generate_summary(content_id: int) -> Dict[str, Any]:
    """
    Background task: Generate summary for content.

    Args:
        content_id: ID of content to summarize

    Returns:
        Result dict
    """
    logger.info("task_generate_summary_start", content_id=content_id)

    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                f"{settings.SUMMARIZER_URL}/summarize",
                json={"content_id": content_id}
            )

            response.raise_for_status()
            result = response.json()

            logger.info("task_generate_summary_success", content_id=content_id)
            return {"status": "success", "result": result}

    except Exception as e:
        logger.error("task_generate_summary_failed", content_id=content_id, error=str(e))
        return {"status": "error", "error": str(e)}


def process_content_pipeline(content_id: int) -> Dict[str, Any]:
    """
    Full pipeline: Embedding → Summary.

    Args:
        content_id: ID of content to process

    Returns:
        Result dict
    """
    logger.info("task_pipeline_start", content_id=content_id)

    results = {}

    # Step 1: Generate embedding
    embedding_result = generate_embedding(content_id)
    results['embedding'] = embedding_result

    if embedding_result['status'] != 'success':
        logger.error("task_pipeline_embedding_failed", content_id=content_id)
        return results

    # Step 2: Generate summary
    summary_result = generate_summary(content_id)
    results['summary'] = summary_result

    logger.info("task_pipeline_completed", content_id=content_id)
    return results
