"""Shared asynchronous Redis client."""

from redis.asyncio import Redis, from_url

from config.settings import settings

redis_client: Redis = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


def get_redis() -> Redis:
    return redis_client


async def close_redis() -> None:
    await redis_client.aclose()
