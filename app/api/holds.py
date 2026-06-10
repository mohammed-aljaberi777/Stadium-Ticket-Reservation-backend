"""Seat-hold endpoints (Redis-backed 5-minute locks)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import (
    RateLimitExceeded,
    client_ip,
    enforce_rate_limit,
    raise_429,
)
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.hold import (
    HoldCreate,
    HoldListItem,
    HoldListResponse,
    HoldResponse,
)
from app.services import hold as hold_service

router = APIRouter(tags=["holds"])


@router.post(
    "/v1/matches/{match_id}/holds",
    response_model=HoldResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_hold(
    match_id: UUID,
    body: HoldCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HoldResponse:
    """Lock the given seats for the current user for 5 minutes."""
    # --- Rate limits: 10/min/user, 20/min/IP ---
    ip = client_ip(request)
    try:
        await enforce_rate_limit(
            redis_client, f"rl:hold:user:{current_user.id}", limit=10, window_seconds=60
        )
        await enforce_rate_limit(
            redis_client, f"rl:hold:ip:{ip}", limit=20, window_seconds=60
        )
    except RateLimitExceeded as exc:
        raise_429(exc)

    try:
        result = await hold_service.create_hold(
            db,
            redis_client,
            user_id=current_user.id,
            match_id=match_id,
            match_seat_ids=body.match_seat_ids,
        )
    except hold_service.HoldError as exc:
        # Map service error codes to HTTP status codes
        status_map = {
            "MATCH_NOT_FOUND": http_status.HTTP_404_NOT_FOUND,
            "SEATS_NOT_FOUND": http_status.HTTP_404_NOT_FOUND,
            "SEAT_NOT_AVAILABLE": http_status.HTTP_409_CONFLICT,
            "SEAT_ALREADY_HELD": http_status.HTTP_409_CONFLICT,
            "CAP_EXCEEDED": http_status.HTTP_403_FORBIDDEN,
        }
        code = status_map.get(exc.code, http_status.HTTP_400_BAD_REQUEST)
        raise HTTPException(
            status_code=code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        ) from exc

    return HoldResponse(**result)


@router.delete(
    "/v1/holds/{hold_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def release_hold(
    hold_id: UUID,
    redis_client: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Release a hold early — seats become AVAILABLE again immediately."""
    try:
        await hold_service.release_hold(redis_client, current_user.id, hold_id)
    except hold_service.HoldError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.get(
    "/v1/holds/me",
    response_model=HoldListResponse,
)
async def list_my_holds(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HoldListResponse:
    """List the current user's active holds with seat metadata."""
    holds = await hold_service.list_user_holds(db, redis_client, current_user.id)
    return HoldListResponse(items=[HoldListItem(**h) for h in holds])
