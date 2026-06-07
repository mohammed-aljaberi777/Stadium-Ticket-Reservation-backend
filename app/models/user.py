from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import UserRole


class User(BaseModel):
    """A person who uses the system: a fan, an admin, or a gate scanner."""

    __tablename__ = "users"

    # Login identifier. unique=True stops two accounts sharing one email.
    # index=True makes "find user by email" (every login) fast.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # We store a bcrypt HASH, never the real password.
    password_hash: Mapped[str] = mapped_column(String(255))

    full_name: Mapped[str] = mapped_column(String(120))

    # Stored as a PostgreSQL ENUM so only the three valid roles can ever be saved.
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"),
        default=UserRole.FAN,
    )

    # Soft-disable an account without deleting it (keeps booking history intact).
    is_active: Mapped[bool] = mapped_column(default=True)
