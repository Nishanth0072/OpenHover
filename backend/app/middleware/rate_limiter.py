"""
Open-Brain Backend — Redis-Backed Rate Limiter

Implements a sliding window rate limiter using Redis Sorted Sets (ZSET).
Configurable per-endpoint limits (general API vs AI chat).
"""

import time
import uuid
import redis.asyncio as aioredis
from loguru import logger

from app.config import settings


async def check_rate_limit(
    redis_client: aioredis.Redis,
    user_id: str,
    endpoint: str = "general",
) -> bool:
    """
    Check if a request is within the rate limit.

    Uses a Redis Sorted Set (ZSET) sliding window:
    - Key: rate_limit:{user_id}:{endpoint}
    - Each request adds a unique member scored by its timestamp
    - Entries older than 60 seconds are pruned before checking
    - Limit: configurable per endpoint type

    Args:
        redis_client: Redis connection
        user_id: The authenticated user's ID
        endpoint: Endpoint category ("general" or "ai_chat")

    Returns:
        True if the request is allowed, False if rate-limited.
    """
    # Determine the limit based on endpoint type
    if endpoint == "ai_chat":
        max_requests = settings.rate_limit_ai_requests_per_minute
    else:
        max_requests = settings.rate_limit_requests_per_minute

    now = time.time()
    window_start = now - 60  # 60-second sliding window
    key = f"rate_limit:{user_id}:{endpoint}"

    # Unique member to handle concurrent requests at the same timestamp
    member = f"{now}:{uuid.uuid4()}"

    try:
        pipe = redis_client.pipeline()
        # Remove entries older than the sliding window
        pipe.zremrangebyscore(key, 0, window_start)
        # Add the current request
        pipe.zadd(key, {member: now})
        # Count requests in the window
        pipe.zcard(key)
        # Auto-expire the key after 2 minutes (cleanup safety net)
        pipe.expire(key, 120)
        results = await pipe.execute()

        current_count = results[2]

        if current_count > max_requests:
            logger.warning(
                f"Rate limit exceeded for user {user_id} on {endpoint}: "
                f"{current_count}/{max_requests} requests/min"
            )
            # Remove the added member so it doesn't inflate future evaluations (no lockout extension on retry)
            await redis_client.zrem(key, member)
            return False

        return True

    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        # Fail open — allow the request if Redis is down
        return True

