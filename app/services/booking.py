"""
The booking transaction — the architectural heart of the system.

Converts a Redis hold into a permanent Postgres booking + tickets,
atomically and race-condition-safely. Follows the 17-step flow from
docs/API.md (steps 2, 3, and 16 — rate limit, cooldown — are deferred
to Phase 3 hardening).
"""

import json
import secrets
from decimal import Decimal
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_qr_token
from app.models.booking import Booking
from app.models.enums import BookingStatus, MatchSeatStatus, TicketStatus
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.models.team import Team
from app.models.ticket import Ticket
from app.services.hold import hold_group_key, hold_seat_key, user_holds_key


class BookingError(Exception):
    """Raised when a booking attempt fails. The API layer converts to HTTP."""

    def __init__(
        self, message: str, code: str, details: dict | None = None
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


def _generate_reference_code(home_team: Team, year: int) -> str:
    """
    Human-friendly reference like 'FCB-2026-A4F2K9'.

    Real systems often use a wider alphabet (Crockford base32) for shorter,
    less-confusing codes. For us, hex is fine.
    """
    suffix = secrets.token_hex(3).upper()  # 6 hex chars
    return f"{home_team.short_name}-{year}-{suffix}"


async def create_booking(
    db: AsyncSession,
    redis_client: Redis,
    *,
    user_id: UUID,
    hold_id: UUID,
) -> dict:
    """Run the booking transaction. See the 17-step flow above."""

    # ===== Steps 4-5: verify hold exists, is owned by user, resolve seats =====
    raw = await redis_client.get(hold_group_key(hold_id))
    if raw is None:
        raise BookingError("Hold not found or expired", code="HOLD_NOT_FOUND")

    data = json.loads(raw)
    if data["user_id"] != str(user_id):
        # Don't reveal that someone else's hold exists.
        raise BookingError("Hold not found or expired", code="HOLD_NOT_FOUND")

    match_id = UUID(data["match_id"])
    match_seat_ids = [UUID(s) for s in data["match_seat_ids"]]

    # ===== Step 6: Postgres transaction begins (implicit at first query) =====
    # Fetch match with home_team for reference code + nested response.
    match = await db.scalar(
        select(Match)
        .where(Match.id == match_id)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.stadium),
        )
    )
    if match is None:
        raise BookingError("Match not found", code="MATCH_NOT_FOUND")

    # ===== Step 7: SELECT ... FOR UPDATE — lock the rows =====
    # Any concurrent transaction touching these rows WAITS here until we commit.
    locked_seats = (
        await db.scalars(
            select(MatchSeat)
            .where(MatchSeat.id.in_(match_seat_ids))
            .with_for_update()
        )
    ).all()
    if len(locked_seats) != len(match_seat_ids):
        raise BookingError("Some seats no longer exist", code="SEATS_NOT_FOUND")

    # ===== Step 8: verify all still AVAILABLE =====
    for ms in locked_seats:
        if ms.status != MatchSeatStatus.AVAILABLE:
            raise BookingError(
                f"Seat {ms.id} is no longer available",
                code="SEAT_NOT_AVAILABLE",
            )

    # ===== Step 9: count user's existing CONFIRMED tickets for this match =====
    existing = await db.scalar(
        select(func.count(Ticket.id))
        .join(Booking, Booking.id == Ticket.booking_id)
        .where(
            Booking.user_id == user_id,
            Booking.match_id == match_id,
            Booking.status == BookingStatus.CONFIRMED,
        )
    ) or 0

    # ===== Step 10: cap re-check INSIDE the transaction (final defense) =====
    if existing + len(match_seat_ids) > match.max_tickets_per_user:
        # Exception → SQLAlchemy rolls back automatically. No partial writes.
        raise BookingError(
            f"This would exceed your limit of {match.max_tickets_per_user} "
            f"tickets for this match",
            code="CAP_EXCEEDED",
            details={
                "max_tickets_per_user": match.max_tickets_per_user,
                "confirmed_tickets": existing,
                "requested": len(match_seat_ids),
            },
        )

    # ===== Step 11: process payment (mocked — v1 always succeeds) =====
    # In production: call Stripe/PayPal here. If fail → raise → rollback.

    # ===== Step 12: create booking + tickets =====
    total = sum((ms.price for ms in locked_seats), Decimal("0"))
    reference_code = _generate_reference_code(match.home_team, match.kickoff_at.year)

    new_booking = Booking(
        user_id=user_id,
        match_id=match_id,
        reference_code=reference_code,
        status=BookingStatus.CONFIRMED,
        total_amount=total,
    )
    db.add(new_booking)
    await db.flush()  # gives us new_booking.id without committing yet

    new_tickets: list[Ticket] = []
    for ms in locked_seats:
        ticket_id = uuid4()  # pre-create so we can embed it in the QR
        qr_token = create_qr_token(
            ticket_id=ticket_id, match_id=match_id, user_id=user_id
        )
        new_tickets.append(
            Ticket(
                id=ticket_id,
                booking_id=new_booking.id,
                match_seat_id=ms.id,
                qr_token=qr_token,
                price_paid=ms.price,
                status=TicketStatus.ISSUED,
            )
        )
    db.add_all(new_tickets)

    # ===== Step 13: flip match_seats to BOOKED =====
    for ms in locked_seats:
        ms.status = MatchSeatStatus.BOOKED

    # ===== Step 14: COMMIT — all-or-nothing =====
    await db.commit()

    # ===== Step 15: delete the Redis hold keys (best-effort) =====
    keys = [hold_seat_key(match_id, s) for s in match_seat_ids]
    keys.append(hold_group_key(hold_id))
    await redis_client.delete(*keys)
    await redis_client.srem(user_holds_key(user_id, match_id), str(hold_id))

    # ===== Step 16: cooldown (deferred to Phase 3) =====

    # ===== Step 17: build response with nested seat info =====
    rows = (
        await db.execute(
            select(Ticket, MatchSeat, Seat, Section)
            .join(MatchSeat, MatchSeat.id == Ticket.match_seat_id)
            .join(Seat, Seat.id == MatchSeat.seat_id)
            .join(Section, Section.id == Seat.section_id)
            .where(Ticket.booking_id == new_booking.id)
        )
    ).all()

    tickets_payload = [
        {
            "id": ticket.id,
            "section": section.name,
            "row": seat.row_number,
            "seat": seat.seat_number,
            "price_paid": ticket.price_paid,
            "status": ticket.status,
            "qr_url": f"/v1/tickets/{ticket.id}/qr",
        }
        for ticket, _ms, seat, section in rows
    ]

    return {
        "id": new_booking.id,
        "reference_code": new_booking.reference_code,
        "status": new_booking.status,
        "total_amount": new_booking.total_amount,
        "match": {
            "id": match.id,
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "kickoff_at": match.kickoff_at,
            "stadium": match.stadium.name,
        },
        "tickets": tickets_payload,
        "created_at": new_booking.created_at,
    }
