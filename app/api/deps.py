"""
Reusable FastAPI dependencies used across endpoints.

The most important one is `get_current_user`: any endpoint that adds
`Depends(get_current_user)` automatically requires a valid JWT and gets
the authenticated User handed to it.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

# HTTPBearer reads "Authorization: Bearer <token>" headers.
# auto_error=True returns 403 automatically when the header is missing.
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Verify the JWT and return the authenticated user.

    Raises 401 if the token is missing/invalid/expired, the wrong type (refresh
    used as access), or the user no longer exists / is disabled.
    """
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Make sure this is an access token, not a refresh token.
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type",
        )

    user_id = payload.get("sub")
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer valid",
        )

    return user


def require_role(*allowed_roles: UserRole):
    """
    Factory that returns a dependency requiring the user to have one of the given roles.

    Usage:
        async def admin_only(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def role_checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action",
            )
        return user

    return role_checker
