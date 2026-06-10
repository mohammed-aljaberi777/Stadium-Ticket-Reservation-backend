"""Booking endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import (
    RateLimitExceeded,
    check_cooldown,
    client_ip,
    enforce_rate_limit,
    raise_429,
    set_cooldown,
)
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingCreatedResponse
from app.services import booking as booking_service

# How long the post-booking cooldown lasts.
BOOKING_COOLDOWN_SECONDS = 30

router = APIRouter(tags=["bookings"])


@router.post(
    "/v1/bookings",
    response_model=BookingCreatedResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_booking(
    body: BookingCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> BookingCreatedResponse:
    """Confirm a hold and create a permanent booking + tickets."""
    # --- Rate limit: 5/min/user (anti-bot scripting) ---
    ip = client_ip(request)
    try:
        await enforce_rate_limit(
            redis_client, f"rl:book:user:{current_user.id}", limit=5, window_seconds=60
        )
        await enforce_rate_limit(
            redis_client, f"rl:book:ip:{ip}", limit=10, window_seconds=60
        )
        # --- Cooldown: must wait 30s after last successful booking ---
        await check_cooldown(redis_client, f"cooldown:booking:user:{current_user.id}")
    except RateLimitExceeded as exc:
        raise_429(exc)

    try:
        result = await booking_service.create_booking(
            db,
            redis_client,
            user_id=current_user.id,
            hold_id=body.hold_id,
        )
    except booking_service.BookingError as exc:
        status_map = {
            "HOLD_NOT_FOUND": http_status.HTTP_404_NOT_FOUND,
            "MATCH_NOT_FOUND": http_status.HTTP_404_NOT_FOUND,
            "SEATS_NOT_FOUND": http_status.HTTP_404_NOT_FOUND,
            "SEAT_NOT_AVAILABLE": http_status.HTTP_409_CONFLICT,
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

    # --- On success: start the 30-second cooldown ---
    await set_cooldown(
        redis_client,
        f"cooldown:booking:user:{current_user.id}",
        BOOKING_COOLDOWN_SECONDS,
    )

    return BookingCreatedResponse(**result)
