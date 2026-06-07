import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import TicketStatus

if TYPE_CHECKING:
    from app.models.booking import Booking


class Ticket(BaseModel):
    """A single entry pass with a QR code. Belongs to one booking and one seat."""

    __tablename__ = "tickets"

    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"))
    match_seat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("match_seats.id"))

    qr_token: Mapped[str] = mapped_column(Text, unique=True)  # signed JWT inside the QR
    price_paid: Mapped[Decimal] = mapped_column(Numeric(8, 2))  # snapshot at booking time
    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status"),
        default=TicketStatus.ISSUED,
    )
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)  # NULL until scanned
    scanned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    booking: Mapped["Booking"] = relationship(back_populates="tickets")
