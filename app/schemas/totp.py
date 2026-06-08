"""Request/response shapes for the 2FA endpoints."""

from pydantic import BaseModel, Field


class TOTPSetupResponse(BaseModel):
    """Returned by POST /v1/auth/2fa/setup."""

    secret: str            # base32, for manual entry into the authenticator app
    provisioning_uri: str  # otpauth:// URL — the frontend renders this as a QR
    qr_url: str            # backend endpoint that returns the QR PNG


class TOTPVerifyRequest(BaseModel):
    """Body for POST /v1/auth/2fa/verify and disable."""

    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TOTPDisableRequest(BaseModel):
    """Body for POST /v1/auth/2fa/disable — requires both password and code."""

    password: str
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TOTPStatusResponse(BaseModel):
    """Returned after enabling/disabling."""

    totp_enabled: bool
