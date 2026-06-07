from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Team(BaseModel):
    """A football club, e.g. FC Bayern München or Borussia Dortmund."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    short_name: Mapped[str] = mapped_column(String(10))  # "FCB", "BVB"
    country: Mapped[str] = mapped_column(String(80))
