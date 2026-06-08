"""Booking endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingCreatedResponse
from app.services import booking as booking_service

router = APIRouter(tags=["bookings"])


@router.post(
    "/v1/bookings",
    response_model=BookingCreatedResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_booking(
    body: BookingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> BookingCreatedResponse:
    """Confirm a hold and create a permanent booking + tickets."""
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

    return BookingCreatedResponse(**result)
