from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, text
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

    # --- 2FA (TOTP) ---
    # totp_secret is the per-user base32 secret. Stays NULL until 2FA setup.
    # In production it should be encrypted at rest; for this project we store as text.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    totp_enabled: Mapped[bool] = mapped_column(
        default=False,
        server_default=text("false"),  # for migrations on existing rows
    )
