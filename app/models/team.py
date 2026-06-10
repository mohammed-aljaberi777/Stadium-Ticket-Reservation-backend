from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Team(BaseModel):
    """A football club, e.g. FC Bayern München or Borussia Dortmund."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    short_name: Mapped[str] = mapped_column(String(10))  # "FCB", "BVB"
    country: Mapped[str] = mapped_column(String(80))
    # logo_url can be a regular URL OR a base64 data URI (image uploaded directly).
    # Stored as TEXT to allow base64 strings (which can be 50-500KB).
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
