import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import SectionCategory, SectionTier

if TYPE_CHECKING:
    from app.models.seat import Seat
    from app.models.stadium import Stadium


class Section(BaseModel):
    """An area within a stadium, e.g. Nordkurve (lower tier)."""

    __tablename__ = "sections"

    # Foreign key: this section belongs to one stadium.
    stadium_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stadiums.id"))

    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[SectionCategory] = mapped_column(
        SAEnum(SectionCategory, name="section_category"),
        default=SectionCategory.STANDARD,
    )
    tier: Mapped[SectionTier] = mapped_column(SAEnum(SectionTier, name="section_tier"))

    # Relationships (the convenient ORM navigation).
    stadium: Mapped["Stadium"] = relationship(back_populates="sections")
    seats: Mapped[list["Seat"]] = relationship(back_populates="section")
