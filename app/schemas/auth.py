"""Request/response shapes for the auth endpoints."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """JSON body for POST /v1/auth/register."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    """JSON body for POST /v1/auth/login."""

    email: EmailStr
    password: str
    totp_code: str | None = None  # required only if the user has enabled 2FA


class RefreshRequest(BaseModel):
    """JSON body for POST /v1/auth/refresh."""

    refresh_token: str


class TokenPair(BaseModel):
    """Response returned by /register, /login, and /refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds until the access token expires
