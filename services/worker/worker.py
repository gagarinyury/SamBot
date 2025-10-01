"""Redis Queue worker for background processing."""

import structlog
from redis import Redis
from rq import Worker, Queue, Connection

from config import settings

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger()


if __name__ == '__main__':
    # Connect to Redis
    redis_conn = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB
    )

    # Parse queue names
    queue_names = [q.strip() for q in settings.WORKER_QUEUES.split(',')]

    logger.info(
        "worker_starting",
        redis_host=settings.REDIS_HOST,
        queues=queue_names
    )

    # Start worker
    with Connection(redis_conn):
        worker = Worker(queue_names)
        logger.info("worker_started")
        worker.work()
