import asyncio
import logging
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import BackgroundTasks

from app.config import get_settings
from app.services.document_processor import process_document_async

settings = get_settings()
logger = logging.getLogger('queue_service')


async def enqueue_document_processing(document_id: int, background_tasks: BackgroundTasks) -> str:
    """
    Attempts to enqueue job to Redis/ARQ queue with a fast connection timeout.
    If Redis is unavailable, immediately falls back to FastAPI BackgroundTasks.
    """
    try:
        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        # 200ms timeout check for Redis availability
        pool = await asyncio.wait_for(create_pool(redis_settings), timeout=0.2)
        await pool.enqueue_job('process_document_task', document_id)
        await pool.close()
        logger.info(f'Enqueued document {document_id} to ARQ Redis worker queue')
        return 'arq_redis'
    except Exception as exc:
        logger.debug(f'Redis queue not reachable ({exc}); using FastAPI BackgroundTasks for document {document_id}')
        background_tasks.add_task(process_document_async, document_id)
        return 'in_process_background'
