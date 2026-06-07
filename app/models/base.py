import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root class SQLAlchemy uses to keep track of every model/table we define."""

    # Tell SQLAlchemy that EVERY `datetime` column should be TIMESTAMPTZ
    # (timezone-aware) across the whole project — honoring ADR-010 in one place.
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class BaseModel(Base):
    """
    Abstract base that every table inherits from.

    It creates no table of its own (__abstract__ = True) but gives every real
    table three columns automatically, so we never repeat them:
      - id          : a UUID primary key
      - created_at  : when the row was created (TIMESTAMPTZ)
      - updated_at  : when the row was last changed (TIMESTAMPTZ)
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )
