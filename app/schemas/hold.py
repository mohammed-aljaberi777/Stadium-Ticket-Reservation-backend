"""Hold request and response shapes (the 5-minute seat lock in Redis)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class HoldCreate(BaseModel):
    """POST /v1/matches/{match_id}/holds body."""

    match_seat_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class HoldResponse(BaseModel):
    """Returned by POST /v1/matches/{match_id}/holds."""

    hold_id: uuid.UUID
    match_id: uuid.UUID
    match_seat_ids: list[uuid.UUID]
    expires_at: datetime
    seconds_remaining: int


class HoldSeatInfo(BaseModel):
    """Seat metadata embedded in a hold list response."""

    match_seat_id: uuid.UUID
    section: str
    row: str
    seat: str
    price: Decimal


class HoldListItem(BaseModel):
    hold_id: uuid.UUID
    match_id: uuid.UUID
    seats: list[HoldSeatInfo]
    expires_at: datetime
    seconds_remaining: int


class HoldListResponse(BaseModel):
    items: list[HoldListItem]
