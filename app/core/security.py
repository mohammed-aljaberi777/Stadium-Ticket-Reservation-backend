"""
Low-level security primitives: password hashing and JWT creation/verification.

Nothing in here knows about HTTP, FastAPI, or the database. It just provides
pure helper functions that the auth service will call.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt is the industry-standard password hashing algorithm.
# "deprecated=auto" lets us upgrade the algorithm later without breaking old hashes.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------- Password hashing ----------

def hash_password(plain_password: str) -> str:
    """Turn a plain-text password into a bcrypt hash. Slow on purpose (~250ms)."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check whether a plain-text password matches a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ---------- JWT creation ----------

def create_access_token(subject: str | UUID, role: str) -> str:
    """
    Create a short-lived access token carrying the user's id and role.
    The frontend sends this in the Authorization header on every request.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(subject),   # "subject" — the user id
        "role": role,           # used for authorization checks
        "type": "access",       # so we can reject refresh tokens used as access
        "exp": expire,          # expiration — verified automatically by jose
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | UUID) -> str:
    """
    Create a longer-lived refresh token. The frontend sends this ONLY when its
    access token has expired, to silently obtain a new one.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(subject),
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ---------- JWT decoding/verification ----------

def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and cryptographically verify a JWT.

    Raises `jose.JWTError` if the signature is wrong, the token is malformed,
    or it has expired. The caller is responsible for handling that error.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------- QR-ticket token ----------

def create_qr_token(
    ticket_id: str | UUID,
    match_id: str | UUID,
    user_id: str | UUID,
) -> str:
    """
    Build the signed JWT embedded inside a ticket's QR code.

    No `exp` claim — the ticket's authority is its own `status` (ISSUED / USED /
    REVOKED) in the database, not the token's expiry. The signature is what
    prevents anyone from forging a QR; it carries (ticket_id, match_id, user_id)
    so the gate scanner can sanity-check the displayed name.
    """
    payload = {
        "ticket_id": str(ticket_id),
        "match_id": str(match_id),
        "user_id": str(user_id),
        "type": "ticket",
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
