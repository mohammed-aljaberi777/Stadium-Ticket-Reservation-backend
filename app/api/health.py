from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe: is the process alive? Deliberately does NOT touch the DB or Redis."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
) -> JSONResponse:
    """Readiness probe: can we actually serve traffic (PostgreSQL + Redis reachable)?"""
    checks = {"postgres": "unknown", "redis": "unknown"}
    healthy = True

    # --- Check PostgreSQL ---
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "error"
        healthy = False

    # --- Check Redis ---
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
        healthy = False

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ready" if healthy else "unavailable",
            "checks": checks,
        },
    )
