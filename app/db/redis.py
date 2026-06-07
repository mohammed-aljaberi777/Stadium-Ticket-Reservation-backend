from redis.asyncio import Redis, from_url

from app.core.config import settings

# A shared async Redis client backed by a connection pool.
# decode_responses=True means we get back Python strings instead of raw bytes.
redis_client: Redis = from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> Redis:
    """FastAPI dependency: return the shared Redis client."""
    return redis_client
