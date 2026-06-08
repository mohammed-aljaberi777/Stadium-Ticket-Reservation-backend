"""Ticket endpoints — list, detail, and QR PNG."""

import io
from typing import Annotated
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ticket import TicketListResponse, TicketResponse
from app.services import ticket as ticket_service

router = APIRouter(tags=["tickets"])


@router.get("/v1/tickets/me", response_model=TicketListResponse)
async def list_my_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketListResponse:
    """All tickets owned by the current user, ordered by kickoff time."""
    tickets = await ticket_service.list_user_tickets(db, current_user.id)
    return TicketListResponse(items=tickets)


@router.get("/v1/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketResponse:
    """One ticket detail (owner only)."""
    try:
        data = await ticket_service.get_ticket(db, ticket_id, current_user.id)
    except ticket_service.TicketError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    return TicketResponse(**data)


@router.get(
    "/v1/tickets/{ticket_id}/qr",
    responses={200: {"content": {"image/png": {}}}},
    response_class=Response,
)
async def get_ticket_qr(
    ticket_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """
    Return the QR code PNG for this ticket.

    The QR image encodes the signed JWT (qr_token). A scanner reads the QR,
    sends the token to POST /v1/verify, and the gate decides ENTRY / DENY.
    """
    try:
        token = await ticket_service.get_ticket_qr_token(
            db, ticket_id, current_user.id
        )
    except ticket_service.TicketError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc

    # Build the QR image in memory and return as PNG bytes.
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
