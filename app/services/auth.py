"""
Business logic for authentication.

This module knows nothing about HTTP. It takes plain Python arguments and
returns plain Python results (or raises AuthError on failure). The API layer
(app/api/auth.py) translates HTTP requests into service calls and service
results back into HTTP responses.
"""

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import TokenPair

# Precomputed bcrypt hash, used only as a placeholder when the email doesn't exist
# so authenticate_user spends roughly the same time whether or not the user is real.
# This prevents an attacker from learning which emails are registered by measuring
# response times. (See `authenticate_user` below.)
_DUMMY_HASH = hash_password("___this_can_never_be_a_real_password___")


class AuthError(Exception):
    """Raised when authentication fails. The API layer converts this to a 4xx response."""

    def __init__(self, message: str, code: str = "AUTH_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


# ---------- Registration ----------

async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
) -> User:
    """Create a new FAN account. Raises AuthError if the email is already taken."""
    email = email.lower()  # normalize: 'Anna@x.com' == 'anna@x.com'

    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise AuthError("Email already registered", code="EMAIL_TAKEN")

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.FAN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)  # populate id, created_at from the database
    return user


# ---------- Login ----------

async def authenticate_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    """
    Verify email + password.

    On failure, ALWAYS raise the same message ('Invalid email or password'),
    regardless of whether the email was unknown or the password was wrong.
    This prevents email-enumeration: an attacker should not be able to learn
    which emails are registered by varying the input.
    """
    user = await db.scalar(select(User).where(User.email == email.lower()))

    if user is None:
        # Spend roughly the same time as a real verify, so timing doesn't leak info.
        verify_password(password, _DUMMY_HASH)
        raise AuthError("Invalid email or password", code="INVALID_CREDENTIALS")

    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", code="INVALID_CREDENTIALS")

    if not user.is_active:
        raise AuthError("Account is disabled", code="ACCOUNT_DISABLED")

    return user


# ---------- Token issuance ----------

def issue_token_pair(user: User) -> TokenPair:
    """Build the {access, refresh} token pair returned by login/register/refresh."""
    return TokenPair(
        access_token=create_access_token(subject=user.id, role=user.role.value),
        refresh_token=create_refresh_token(subject=user.id),
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------- Refresh ----------

async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenPair:
    """Exchange a valid refresh token for a fresh token pair."""
    try:
        payload = decode_token(refresh_token)
    except JWTError as exc:
        raise AuthError("Invalid or expired refresh token", code="INVALID_TOKEN") from exc

    if payload.get("type") != "refresh":
        # Don't let access tokens be used as refresh tokens, or vice versa.
        raise AuthError("Wrong token type", code="WRONG_TOKEN_TYPE")

    user_id = payload.get("sub")
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise AuthError("User no longer valid", code="USER_INVALID")

    return issue_token_pair(user)
