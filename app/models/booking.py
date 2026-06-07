import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import BookingStatus

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Booking(BaseModel):
    """A fan's order. One booking can contain many tickets."""

    __tablename__ = "bookings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"))
    reference_code: Mapped[str] = mapped_column(String(20), unique=True)  # "FCB-2026-A4F2"
    status: Mapped[BookingStatus] = mapped_column(
        SAEnum(BookingStatus, name="booking_status"),
        default=BookingStatus.PENDING,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    # Audit columns for abuse investigation (optional — nullable).
    client_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # One booking has many tickets (the other side is Ticket.booking).
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="booking")
