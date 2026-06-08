"""Business logic for ticket endpoints."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.booking import Booking
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.models.stadium import Stadium
from app.models.team import Team
from app.models.ticket import Ticket


class TicketError(Exception):
    def __init__(self, message: str, code: str) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


def _ticket_query_for_user(user_id: UUID):
    """
    Shared JOIN: ticket -> booking -> match (home, away, stadium)
                 ticket -> match_seat -> seat -> section.

    Returns rows of (Ticket, Booking, MatchSeat, Seat, Section, Match,
    home_team, away_team, Stadium) for every ticket owned by the user.
    """
    home = aliased(Team, name="home_team")
    away = aliased(Team, name="away_team")
    return (
        select(Ticket, Booking, MatchSeat, Seat, Section, Match, home, away, Stadium)
        .join(Booking, Booking.id == Ticket.booking_id)
        .join(MatchSeat, MatchSeat.id == Ticket.match_seat_id)
        .join(Seat, Seat.id == MatchSeat.seat_id)
        .join(Section, Section.id == Seat.section_id)
        .join(Match, Match.id == Booking.match_id)
        .join(home, home.id == Match.home_team_id)
        .join(away, away.id == Match.away_team_id)
        .join(Stadium, Stadium.id == Match.stadium_id)
        .where(Booking.user_id == user_id)
    )


def _row_to_ticket_dict(row) -> dict:
    """Turn one query row into the response dict shape."""
    t, b, _ms, s, sec, m, home_team, away_team, stadium = row
    return {
        "id": t.id,
        "booking_id": b.id,
        "reference_code": b.reference_code,
        "seat": {
            "section": sec.name,
            "row": s.row_number,
            "seat": s.seat_number,
        },
        "match": {
            "id": m.id,
            "home_team": home_team.name,
            "away_team": away_team.name,
            "kickoff_at": m.kickoff_at,
            "stadium": stadium.name,
        },
        "price_paid": t.price_paid,
        "status": t.status,
        "qr_url": f"/v1/tickets/{t.id}/qr",
        "issued_at": t.issued_at,
        "used_at": t.used_at,
    }


async def list_user_tickets(db: AsyncSession, user_id: UUID) -> list[dict]:
    q = _ticket_query_for_user(user_id).order_by(Match.kickoff_at)
    rows = (await db.execute(q)).all()
    return [_row_to_ticket_dict(r) for r in rows]


async def get_ticket(db: AsyncSession, ticket_id: UUID, user_id: UUID) -> dict:
    q = _ticket_query_for_user(user_id).where(Ticket.id == ticket_id)
    row = (await db.execute(q)).first()
    if row is None:
        raise TicketError("Ticket not found", code="TICKET_NOT_FOUND")
    return _row_to_ticket_dict(row)


async def get_ticket_qr_token(db: AsyncSession, ticket_id: UUID, user_id: UUID) -> str:
    """Return just the qr_token string for QR rendering."""
    q = (
        select(Ticket.qr_token)
        .join(Booking, Booking.id == Ticket.booking_id)
        .where(Ticket.id == ticket_id, Booking.user_id == user_id)
    )
    token = await db.scalar(q)
    if token is None:
        raise TicketError("Ticket not found", code="TICKET_NOT_FOUND")
    return token
