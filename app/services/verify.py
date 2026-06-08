"""
Gate verification — the matchday endpoint.

Verifies a QR-encoded JWT, runs an atomic UPDATE to mark the ticket USED,
and returns enough info for the scanner UI to display the seat + buyer name.
"""

from uuid import UUID

from jose import JWTError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.security import decode_token
from app.models.booking import Booking
from app.models.enums import MatchStatus, TicketStatus
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.models.team import Team
from app.models.ticket import Ticket
from app.models.user import User


class VerifyError(Exception):
    """Raised when a scan should be REJECTED. Carries the reason code."""

    def __init__(self, reason: str, details: dict | None = None) -> None:
        self.reason = reason
        self.details = details or {}
        super().__init__(reason)


async def verify_ticket(
    db: AsyncSession,
    scanner_user_id: UUID,
    qr_token: str,
) -> dict:
    """
    Verify the QR-encoded JWT and atomically mark the ticket USED.

    Returns a dict with APPROVED + ticket info.
    Raises VerifyError(reason=...) for any REJECTED outcome.
    """

    # ---- 1. Verify the JWT signature ----
    try:
        payload = decode_token(qr_token)
    except JWTError:
        raise VerifyError("INVALID_TOKEN")

    if payload.get("type") != "ticket":
        raise VerifyError("WRONG_TOKEN_TYPE")

    ticket_id_str = payload.get("ticket_id")
    if not ticket_id_str:
        raise VerifyError("INVALID_TOKEN")
    try:
        ticket_id = UUID(ticket_id_str)
    except (ValueError, TypeError):
        raise VerifyError("INVALID_TOKEN")

    # ---- 2. Look up everything we need to render the response ----
    home = aliased(Team, name="home")
    away = aliased(Team, name="away")

    info_q = (
        select(Ticket, Section, Seat, Match, home, away, User)
        .join(Booking, Booking.id == Ticket.booking_id)
        .join(MatchSeat, MatchSeat.id == Ticket.match_seat_id)
        .join(Seat, Seat.id == MatchSeat.seat_id)
        .join(Section, Section.id == Seat.section_id)
        .join(Match, Match.id == Booking.match_id)
        .join(home, home.id == Match.home_team_id)
        .join(away, away.id == Match.away_team_id)
        .join(User, User.id == Booking.user_id)
        .where(Ticket.id == ticket_id)
    )
    row = (await db.execute(info_q)).first()
    if row is None:
        raise VerifyError("TICKET_NOT_FOUND")

    ticket, section, seat, match, home_team, away_team, owner = row

    # ---- 3. Match must be in an active window ----
    if match.status in {MatchStatus.COMPLETED, MatchStatus.CANCELLED}:
        raise VerifyError(
            "MATCH_NOT_ACTIVE",
            details={"match_status": match.status.value},
        )

    # ---- 4. THE atomic UPDATE — the critical step ----
    # The WHERE status='ISSUED' makes "check + consume" one indivisible op.
    # Two scanners racing on the same QR: Postgres serializes, only ONE wins.
    upd = (
        update(Ticket)
        .where(Ticket.id == ticket_id, Ticket.status == TicketStatus.ISSUED)
        .values(
            status=TicketStatus.USED,
            used_at=func.now(),
            scanned_by_user_id=scanner_user_id,
        )
        .returning(Ticket.id)
    )
    result = await db.execute(upd)
    updated_id = result.scalar_one_or_none()

    if updated_id is None:
        # No row updated → status wasn't ISSUED. Capture the values BEFORE
        # rolling back — rollback expires all loaded attributes, and the
        # next attribute access would try to lazy-load (illegal in async).
        prev_status = ticket.status
        prev_used_at = ticket.used_at
        await db.rollback()

        if prev_status == TicketStatus.USED:
            raise VerifyError(
                "ALREADY_USED",
                details={"used_at": prev_used_at.isoformat() if prev_used_at else None},
            )
        if prev_status == TicketStatus.REVOKED:
            raise VerifyError("TICKET_REVOKED")
        raise VerifyError(
            "UNEXPECTED_STATUS", details={"status": prev_status.value}
        )

    await db.commit()

    # ---- 5. APPROVED response ----
    return {
        "result": "APPROVED",
        "ticket": {
            "id": ticket.id,
            "user_full_name": owner.full_name,
            "section": section.name,
            "row": seat.row_number,
            "seat": seat.seat_number,
            "match": f"{home_team.name} vs {away_team.name}",
        },
    }
