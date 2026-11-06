"""Database and async helpers for synchronous Celery task entry points."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config.settings import settings

# Celery tasks create their own event loop per invocation. NullPool avoids
# carrying asyncpg connections across those short-lived loops.
worker_engine = create_async_engine(settings.database_url, poolclass=NullPool, pool_pre_ping=True)
WorkerSession = async_sessionmaker(worker_engine, expire_on_commit=False)


def run_async(coro):
    async def run_and_dispose():
        try:
            return await coro
        finally:
            await worker_engine.dispose()

    return asyncio.run(run_and_dispose())
