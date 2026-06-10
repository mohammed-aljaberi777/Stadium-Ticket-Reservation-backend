"""How a User is shown to API clients."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class UserResponse(BaseModel):
    """Public shape of a user (NEVER includes password_hash or totp_secret)."""

    # from_attributes=True lets Pydantic read fields off a SQLAlchemy model object
    # — so we can return `UserResponse.model_validate(user)` directly.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    totp_enabled: bool
    created_at: datetime
