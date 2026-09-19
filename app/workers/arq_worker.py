import logging
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.config import get_settings
from app.services.document_processor import process_document_async

settings = get_settings()
logger = logging.getLogger('arq_worker')


async def startup(ctx):
    logger.info('ARQ Document Intelligence Worker started')


async def shutdown(ctx):
    logger.info('ARQ Document Intelligence Worker stopped')


async def process_document_task(ctx, document_id: int):
    """ARQ job to process document asynchronously in a distributed worker."""
    logger.info(f'Starting ARQ background processing for document {document_id}')
    await process_document_async(document_id)
    return {'document_id': document_id, 'status': 'completed'}


class WorkerSettings:
    functions = [process_document_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    poll_delay = 0.5
