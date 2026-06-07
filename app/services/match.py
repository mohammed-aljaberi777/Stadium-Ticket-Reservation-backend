"""Business logic for match browsing."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import Competition, MatchSeatStatus, MatchStatus
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.schemas.section import SectionSummary


def _with_relationships(query):
    """Eagerly load home_team, away_team, and stadium with the match."""
    return query.options(
        selectinload(Match.home_team),
        selectinload(Match.away_team),
        selectinload(Match.stadium),
    )


async def list_matches(
    db: AsyncSession,
    *,
    status: MatchStatus | None = None,
    competition: Competition | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Match], int]:
    """Return (matches, total_count) honoring the given filters and pagination."""

    query = _with_relationships(select(Match))
    count_query = select(func.count(Match.id))

    # Apply the same filters to both the data query and the count query
    if status is not None:
        query = query.where(Match.status == status)
        count_query = count_query.where(Match.status == status)
    if competition is not None:
        query = query.where(Match.competition == competition)
        count_query = count_query.where(Match.competition == competition)
    if from_date is not None:
        query = query.where(Match.kickoff_at >= from_date)
        count_query = count_query.where(Match.kickoff_at >= from_date)
    if to_date is not None:
        query = query.where(Match.kickoff_at <= to_date)
        count_query = count_query.where(Match.kickoff_at <= to_date)

    # Earliest kickoff first; cap by limit/offset
    query = query.order_by(Match.kickoff_at).limit(limit).offset(offset)

    matches = (await db.scalars(query)).all()
    total = await db.scalar(count_query) or 0
    return list(matches), total


async def get_match(db: AsyncSession, match_id: UUID) -> Match | None:
    """Get one match by id with all relationships eagerly loaded. None if not found."""
    query = _with_relationships(select(Match).where(Match.id == match_id))
    return await db.scalar(query)


async def get_section_summaries(
    db: AsyncSession, match_id: UUID
) -> list[SectionSummary]:
    """
    Return one row per section: how many seats are AVAILABLE vs total,
    and the price range. Used by the seating-chart overview.

    This is a single SQL query with GROUP BY — much faster than looping
    sections and counting in Python.
    """
    query = (
        select(
            Section.id.label("section_id"),
            Section.name,
            Section.category,
            Section.tier,
            # COUNT the rows where status = AVAILABLE
            func.count(
                case((MatchSeat.status == MatchSeatStatus.AVAILABLE, 1))
            ).label("available_seats"),
            func.count(MatchSeat.id).label("total_seats"),
            func.min(MatchSeat.price).label("min_price"),
            func.max(MatchSeat.price).label("max_price"),
        )
        .join(Seat, Seat.section_id == Section.id)
        .join(
            MatchSeat,
            (MatchSeat.seat_id == Seat.id) & (MatchSeat.match_id == match_id),
        )
        .group_by(Section.id, Section.name, Section.category, Section.tier)
        .order_by(Section.name)
    )
    result = await db.execute(query)
    return [SectionSummary.model_validate(row, from_attributes=True) for row in result.all()]
