"""Public match-browsing endpoints. No authentication required."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status  # aliased so it doesn't collide with the `status` query param
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import Competition, MatchStatus
from app.schemas.match import MatchListResponse, MatchResponse
from app.schemas.section import SectionSummaryListResponse
from app.services import match as match_service

router = APIRouter(prefix="/v1/matches", tags=["matches"])


@router.get("", response_model=MatchListResponse)
async def list_matches(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[MatchStatus | None, Query(description="Filter by match status")] = None,
    competition: Annotated[Competition | None, Query(description="Filter by competition")] = None,
    from_date: Annotated[datetime | None, Query(description="Kickoff on or after")] = None,
    to_date: Annotated[datetime | None, Query(description="Kickoff on or before")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MatchListResponse:
    """List upcoming matches with optional filters and pagination."""
    matches, total = await match_service.list_matches(
        db,
        status=status,
        competition=competition,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return MatchListResponse(
        items=[MatchResponse.model_validate(m) for m in matches],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MatchResponse:
    """Get details for a single match."""
    match = await match_service.get_match(db, match_id)
    if match is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Match not found")
    return MatchResponse.model_validate(match)


@router.get("/{match_id}/sections", response_model=SectionSummaryListResponse)
async def get_section_summaries(
    match_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SectionSummaryListResponse:
    """Per-section availability + price summary, used to render the seating-chart overview."""
    # 404 if the match itself doesn't exist (gives a clearer error than empty list)
    if await match_service.get_match(db, match_id) is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Match not found"
        )
    items = await match_service.get_section_summaries(db, match_id)
    return SectionSummaryListResponse(items=items)
