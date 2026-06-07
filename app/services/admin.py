"""
Admin business logic: create teams, stadiums, and matches.

Like the auth service, this module knows nothing about HTTP. It just takes
plain Python arguments and either returns model instances or raises
ServiceError, which the API layer converts to the appropriate HTTP response.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import MatchSeatStatus
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.models.stadium import Stadium
from app.models.team import Team
from app.schemas.match import MatchCreate
from app.schemas.section import SectionCreate
from app.schemas.seat import MatchInventoryCreate, SeatBulkCreate
from app.schemas.stadium import StadiumCreate
from app.schemas.team import TeamCreate


class ServiceError(Exception):
    """Raised when an admin operation fails for a business reason."""

    def __init__(self, message: str, code: str = "SERVICE_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


# ---------- Teams ----------

async def create_team(db: AsyncSession, data: TeamCreate) -> Team:
    existing = await db.scalar(select(Team).where(Team.name == data.name))
    if existing is not None:
        raise ServiceError(f"Team '{data.name}' already exists", code="TEAM_EXISTS")

    team = Team(
        name=data.name,
        short_name=data.short_name,
        country=data.country,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


# ---------- Stadiums ----------

async def create_stadium(db: AsyncSession, data: StadiumCreate) -> Stadium:
    stadium = Stadium(
        name=data.name,
        city=data.city,
        capacity=data.capacity,
    )
    db.add(stadium)
    await db.commit()
    await db.refresh(stadium)
    return stadium


# ---------- Matches ----------

async def create_match(db: AsyncSession, data: MatchCreate) -> Match:
    # --- business-rule validation ---
    if data.home_team_id == data.away_team_id:
        raise ServiceError("Home and away team must be different", code="SAME_TEAM")
    if data.sales_open_at >= data.sales_close_at:
        raise ServiceError("Sales must open before they close", code="INVALID_SALES_WINDOW")
    if data.sales_close_at > data.kickoff_at:
        raise ServiceError("Sales must close before or at kickoff", code="SALES_AFTER_KICKOFF")

    # --- verify referenced rows exist (clearer errors than relying on FK fail) ---
    if await db.get(Stadium, data.stadium_id) is None:
        raise ServiceError("Stadium not found", code="STADIUM_NOT_FOUND")
    if await db.get(Team, data.home_team_id) is None:
        raise ServiceError("Home team not found", code="HOME_TEAM_NOT_FOUND")
    if await db.get(Team, data.away_team_id) is None:
        raise ServiceError("Away team not found", code="AWAY_TEAM_NOT_FOUND")

    match = Match(
        stadium_id=data.stadium_id,
        home_team_id=data.home_team_id,
        away_team_id=data.away_team_id,
        competition=data.competition,
        kickoff_at=data.kickoff_at,
        sales_open_at=data.sales_open_at,
        sales_close_at=data.sales_close_at,
        max_tickets_per_user=data.max_tickets_per_user,
        # status defaults to SCHEDULED in the model
    )
    db.add(match)
    await db.commit()

    # Re-fetch with relationships loaded for a nice nested response
    query = (
        select(Match)
        .where(Match.id == match.id)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.stadium),
        )
    )
    return await db.scalar(query)


# ---------- Sections ----------

async def create_section(
    db: AsyncSession, stadium_id: UUID, data: SectionCreate
) -> Section:
    if await db.get(Stadium, stadium_id) is None:
        raise ServiceError("Stadium not found", code="STADIUM_NOT_FOUND")

    section = Section(
        stadium_id=stadium_id,
        name=data.name,
        category=data.category,
        tier=data.tier,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


# ---------- Seats (bulk) ----------

async def create_seats_bulk(
    db: AsyncSession, section_id: UUID, data: SeatBulkCreate
) -> int:
    if await db.get(Section, section_id) is None:
        raise ServiceError("Section not found", code="SECTION_NOT_FOUND")

    seats = [
        Seat(section_id=section_id, row_number=row, seat_number=str(num))
        for row in data.rows
        for num in range(1, data.seats_per_row + 1)
    ]
    db.add_all(seats)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # The (section_id, row_number, seat_number) UNIQUE constraint kicked in.
        raise ServiceError(
            "Some seats already exist in this section",
            code="DUPLICATE_SEATS",
        ) from exc

    return len(seats)


# ---------- Match inventory ----------

async def generate_match_inventory(
    db: AsyncSession, match_id: UUID, data: MatchInventoryCreate
) -> tuple[int, int]:
    """
    Create one match_seats row per seat in each priced section.

    Returns (rows_created, sections_priced).
    """
    if await db.get(Match, match_id) is None:
        raise ServiceError("Match not found", code="MATCH_NOT_FOUND")

    total_created = 0
    for sp in data.section_prices:
        section = await db.get(Section, sp.section_id)
        if section is None:
            raise ServiceError(
                f"Section {sp.section_id} not found", code="SECTION_NOT_FOUND"
            )

        # All seats in this section
        seats = (
            await db.scalars(select(Seat).where(Seat.section_id == sp.section_id))
        ).all()

        match_seats = [
            MatchSeat(
                match_id=match_id,
                seat_id=seat.id,
                price=sp.price,
                status=MatchSeatStatus.AVAILABLE,
            )
            for seat in seats
        ]
        db.add_all(match_seats)
        total_created += len(match_seats)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # The (match_id, seat_id) UNIQUE constraint caught a duplicate run.
        raise ServiceError(
            "Inventory has already been generated for this match",
            code="DUPLICATE_INVENTORY",
        ) from exc

    return total_created, len(data.section_prices)
