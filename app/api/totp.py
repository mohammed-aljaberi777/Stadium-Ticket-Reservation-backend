"""2FA endpoints — setup, verify (activate), disable, and QR PNG."""

import io
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.totp import (
    TOTPDisableRequest,
    TOTPSetupResponse,
    TOTPStatusResponse,
    TOTPVerifyRequest,
)
from app.services import totp as totp_service

router = APIRouter(prefix="/v1/auth/2fa", tags=["2fa"])


@router.post("/setup", response_model=TOTPSetupResponse)
async def setup_2fa(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TOTPSetupResponse:
    """
    Generate a secret + provisioning URI. Does NOT enable 2FA yet — the user
    must scan and then call /verify with a valid code to actually turn it on.
    """
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="2FA is already enabled",
        )

    # Always generate a fresh secret on setup — never reuse an old one.
    secret = totp_service.generate_secret()
    uri = totp_service.provisioning_uri(secret, current_user.email)

    # Stash the secret on the user, but DON'T set totp_enabled yet.
    current_user.totp_secret = secret
    await db.commit()

    return TOTPSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_url="/v1/auth/2fa/qr",
    )


@router.get("/qr", responses={200: {"content": {"image/png": {}}}}, response_class=Response)
async def get_setup_qr(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Render the user's pending provisioning URI as a scannable QR PNG."""
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="No 2FA setup in progress — call /setup first",
        )

    uri = totp_service.provisioning_uri(
        current_user.totp_secret, current_user.email
    )
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.post("/verify", response_model=TOTPStatusResponse)
async def verify_2fa(
    body: TOTPVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TOTPStatusResponse:
    """Submit the first 6-digit code from the authenticator app to activate 2FA."""
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="2FA is already enabled",
        )
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No 2FA setup in progress — call /setup first",
        )

    if not totp_service.verify_code(current_user.totp_secret, body.code):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOTP_INVALID", "message": "Invalid code"},
        )

    current_user.totp_enabled = True
    await db.commit()
    return TOTPStatusResponse(totp_enabled=True)


@router.post("/disable", response_model=TOTPStatusResponse)
async def disable_2fa(
    body: TOTPDisableRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TOTPStatusResponse:
    """Turn 2FA off — requires the current password AND a valid code."""
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="2FA is not enabled",
        )

    if not verify_password(body.password, current_user.password_hash):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Wrong password",
        )
    if not totp_service.verify_code(current_user.totp_secret or "", body.code):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOTP_INVALID", "message": "Invalid code"},
        )

    current_user.totp_enabled = False
    current_user.totp_secret = None
    await db.commit()
    return TOTPStatusResponse(totp_enabled=False)
