"""Booking request and response shapes."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import BookingStatus, TicketStatus


class BookingCreate(BaseModel):
    """POST /v1/bookings body."""

    hold_id: uuid.UUID
    # In a real system: payment_method_token from Stripe / PayPal.
    # For v1 we mock — the booking always succeeds.


class BookingMatchSummary(BaseModel):
    """Lightweight match info embedded in a booking response."""

    id: uuid.UUID
    home_team: str
    away_team: str
    kickoff_at: datetime
    stadium: str


class TicketInBooking(BaseModel):
    """One ticket inside a booking response (with QR URL)."""

    id: uuid.UUID
    section: str
    row: str
    seat: str
    price_paid: Decimal
    status: TicketStatus
    qr_url: str


class BookingCreatedResponse(BaseModel):
    """POST /v1/bookings response — the full order + every ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_code: str
    status: BookingStatus
    total_amount: Decimal
    match: BookingMatchSummary
    tickets: list[TicketInBooking]
    created_at: datetime
