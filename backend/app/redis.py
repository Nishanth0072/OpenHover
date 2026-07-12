"""
Open-Brain Backend — Redis Connection Manager

Provides async Redis connection pool for caching, rate limiting,
and token blacklisting.
"""

import redis.asyncio as aioredis
from app.config import settings

# Redis connection pool (initialized on app startup)
redis_pool: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """Initialize the Redis connection pool."""
    global redis_pool
    redis_pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    return redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global redis_pool
    if redis_pool:
        await redis_pool.close()
        redis_pool = None


async def get_redis() -> aioredis.Redis:
    """Dependency that returns the Redis connection."""
    if redis_pool is None:
        raise RuntimeError("Redis is not initialized. Call init_redis() first.")
    return redis_pool
