"""Redis Queue client for background tasks."""

import structlog
from typing import Optional

logger = structlog.get_logger()

# Try to import Redis/RQ
try:
    from redis import Redis
    from rq import Queue
    import os

    redis_conn = Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0
    )

    embedding_queue = Queue('embedding', connection=redis_conn)
    summarization_queue = Queue('summarization', connection=redis_conn)

    REDIS_AVAILABLE = True
    logger.info("redis_queue_initialized")

except Exception as e:
    REDIS_AVAILABLE = False
    embedding_queue = None
    summarization_queue = None
    logger.warning("redis_queue_unavailable", error=str(e))


def enqueue_embedding(content_id: int) -> Optional[str]:
    """
    Enqueue embedding generation task.

    Args:
        content_id: ID of content

    Returns:
        Job ID or None
    """
    if not REDIS_AVAILABLE:
        logger.warning("redis_unavailable_skipping_embedding", content_id=content_id)
        return None

    try:
        job = embedding_queue.enqueue(
            'tasks.process_content_pipeline',
            content_id,
            job_timeout='10m'
        )
        logger.info("embedding_task_enqueued", content_id=content_id, job_id=job.id)
        return job.id
    except Exception as e:
        logger.error("enqueue_embedding_failed", content_id=content_id, error=str(e))
        return None


def enqueue_summarization(content_id: int) -> Optional[str]:
    """
    Enqueue summarization task.

    Args:
        content_id: ID of content

    Returns:
        Job ID or None
    """
    if not REDIS_AVAILABLE:
        logger.warning("redis_unavailable_skipping_summary", content_id=content_id)
        return None

    try:
        job = summarization_queue.enqueue(
            'tasks.generate_summary',
            content_id,
            job_timeout='5m'
        )
        logger.info("summary_task_enqueued", content_id=content_id, job_id=job.id)
        return job.id
    except Exception as e:
        logger.error("enqueue_summary_failed", content_id=content_id, error=str(e))
        return None
