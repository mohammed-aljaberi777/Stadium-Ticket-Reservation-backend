"""Gate-verification endpoint — requires GATE_SCANNER role."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.verify import VerifyRequest, VerifyResponse
from app.services import verify as verify_service

router = APIRouter(tags=["verify"])

RequireScanner = Annotated[User, Depends(require_role(UserRole.GATE_SCANNER))]


@router.post("/v1/verify", response_model=VerifyResponse)
async def verify(
    body: VerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    scanner: RequireScanner,
) -> VerifyResponse:
    """
    Scan a ticket at the stadium gate. Returns APPROVED or REJECTED.

    Both outcomes are HTTP 200 — the verdict is in the response body.
    The scanner app uses `result` to decide what to flash on its screen
    (green check vs. red X) and the `reason` to display a hint.
    """
    try:
        result = await verify_service.verify_ticket(db, scanner.id, body.qr_token)
        return VerifyResponse(**result)
    except verify_service.VerifyError as exc:
        return VerifyResponse(
            result="REJECTED",
            reason=exc.reason,
            details=exc.details,
        )
