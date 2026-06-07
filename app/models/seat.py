import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.section import Section


class Seat(BaseModel):
    """A single physical seat within a section."""

    __tablename__ = "seats"
    __table_args__ = (
        # The same row+seat number can't appear twice in one section.
        UniqueConstraint("section_id", "row_number", "seat_number"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"))
    row_number: Mapped[str] = mapped_column(String(8))   # text: allows "A", "12", etc.
    seat_number: Mapped[str] = mapped_column(String(8))

    section: Mapped["Section"] = relationship(back_populates="seats")
