import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import MatchSeatStatus

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.seat import Seat


class MatchSeat(BaseModel):
    """
    Per-match inventory: one row per seat per match.

    This is the 'heart of the system' — it holds the price and durable status
    of each seat for each match. (Temporary holds live in Redis, not here.)
    """

    __tablename__ = "match_seats"
    __table_args__ = (
        # A seat can only appear once per match.
        UniqueConstraint("match_id", "seat_id"),
    )

    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"))
    seat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seats.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2))  # exact money, never float
    status: Mapped[MatchSeatStatus] = mapped_column(
        SAEnum(MatchSeatStatus, name="match_seat_status"),
        default=MatchSeatStatus.AVAILABLE,
    )

    match: Mapped["Match"] = relationship()
    seat: Mapped["Seat"] = relationship()
