from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.section import Section


class Stadium(BaseModel):
    """A venue, e.g. Allianz Arena."""

    __tablename__ = "stadiums"

    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column()

    # One stadium has many sections (the other side is Section.stadium).
    sections: Mapped[list["Section"]] = relationship(back_populates="stadium")
