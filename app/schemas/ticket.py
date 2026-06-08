"""Ticket response shapes."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import TicketStatus


class TicketSeatInfo(BaseModel):
    section: str
    row: str
    seat: str


class TicketMatchSummary(BaseModel):
    id: uuid.UUID
    home_team: str
    away_team: str
    kickoff_at: datetime
    stadium: str


class TicketResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    reference_code: str
    seat: TicketSeatInfo
    match: TicketMatchSummary
    price_paid: Decimal
    status: TicketStatus
    qr_url: str
    issued_at: datetime
    used_at: datetime | None


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
