"""
Authentication endpoints: register, login, refresh, me.

These are intentionally tiny. They parse the request, call a service, and
return the result. All the actual logic lives in app/services/auth.py.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.user import UserResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """Create a new fan account and return access + refresh tokens."""
    try:
        user = await auth_service.register_user(
            db,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
    except auth_service.AuthError as exc:
        # EMAIL_TAKEN -> 409 Conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc

    return auth_service.issue_token_pair(user)


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """Exchange email + password for a fresh token pair."""
    try:
        user = await auth_service.authenticate_user(
            db,
            email=body.email,
            password=body.password,
        )
    except auth_service.AuthError as exc:
        # ACCOUNT_DISABLED -> 403, everything else -> 401
        code = (
            status.HTTP_403_FORBIDDEN
            if exc.code == "ACCOUNT_DISABLED"
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(status_code=code, detail=exc.message) from exc

    return auth_service.issue_token_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """Exchange a refresh token for a fresh access + refresh pair."""
    try:
        return await auth_service.refresh_access_token(db, body.refresh_token)
    except auth_service.AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)
