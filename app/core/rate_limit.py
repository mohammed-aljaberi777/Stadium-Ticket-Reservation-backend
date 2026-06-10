"""
Redis-backed rate-limiting and cooldown helpers.

Fixed-window counter strategy: INCR a per-key counter, set its TTL on first
use, raise if the counter exceeds the limit before the window expires.
Simple, atomic on Redis's side, and good enough to stop scripted abuse.

For higher accuracy at the window edges, a "sliding window" with sorted
sets is more precise — noted as a future improvement.
"""

from fastapi import HTTPException, Request
from fastapi import status as http_status
from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    """Raised when a Redis counter exceeds the limit."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(retry_after, 1)
        super().__init__(f"Rate limit exceeded, retry after {self.retry_after}s")


async def enforce_rate_limit(
    redis_client: Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Atomically INCR; raise RateLimitExceeded if over the limit."""
    current = await redis_client.incr(key)
    if current == 1:
        # First hit in this window — set the TTL.
        await redis_client.expire(key, window_seconds)
    if current > limit:
        ttl = await redis_client.ttl(key)
        raise RateLimitExceeded(retry_after=ttl)


async def check_cooldown(redis_client: Redis, key: str) -> None:
    """Raise RateLimitExceeded if a cooldown key is still active."""
    ttl = await redis_client.ttl(key)
    if ttl > 0:
        raise RateLimitExceeded(retry_after=ttl)


async def set_cooldown(redis_client: Redis, key: str, seconds: int) -> None:
    """Start a cooldown window."""
    await redis_client.set(key, "1", ex=seconds, nx=True)


def client_ip(request: Request) -> str:
    """Best-effort client IP — honors X-Forwarded-For when behind a proxy."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def raise_429(exc: RateLimitExceeded) -> None:
    """Convert RateLimitExceeded into a 429 response with Retry-After header."""
    raise HTTPException(
        status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many requests. Try again in {exc.retry_after} seconds.",
            "retry_after_seconds": exc.retry_after,
        },
        headers={"Retry-After": str(exc.retry_after)},
    )
