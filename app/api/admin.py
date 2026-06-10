"""Admin endpoints — every route requires role=ADMIN."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from uuid import UUID

from app.schemas.match import MatchCreate, MatchResponse
from app.schemas.section import SectionCreate, SectionResponse
from app.schemas.seat import (
    InventoryGenerationResponse,
    MatchInventoryCreate,
    SeatBulkCreate,
    SeatBulkCreateResponse,
)
from app.schemas.stadium import StadiumCreate, StadiumListResponse, StadiumResponse
from app.schemas.team import TeamCreate, TeamListResponse, TeamResponse
from app.services import admin as admin_service

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# Shorthand so every endpoint's parameter list stays readable.
RequireAdmin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.post("/teams", response_model=TeamResponse, status_code=http_status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> TeamResponse:
    try:
        team = await admin_service.create_team(db, body)
    except admin_service.ServiceError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=exc.message
        ) from exc
    return TeamResponse.model_validate(team)


@router.get("/teams", response_model=TeamListResponse)
async def list_teams(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> TeamListResponse:
    """List all teams — used by the New Match form dropdown."""
    teams = await admin_service.list_teams(db)
    return TeamListResponse(items=[TeamResponse.model_validate(t) for t in teams])


@router.post(
    "/stadiums",
    response_model=StadiumResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_stadium(
    body: StadiumCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> StadiumResponse:
    stadium = await admin_service.create_stadium(db, body)
    return StadiumResponse.model_validate(stadium)


@router.get("/stadiums", response_model=StadiumListResponse)
async def list_stadiums(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> StadiumListResponse:
    """List all stadiums — used by the New Match form dropdown."""
    stadiums = await admin_service.list_stadiums(db)
    return StadiumListResponse(items=[StadiumResponse.model_validate(s) for s in stadiums])


@router.post(
    "/matches",
    response_model=MatchResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_match(
    body: MatchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> MatchResponse:
    try:
        match = await admin_service.create_match(db, body)
    except admin_service.ServiceError as exc:
        # Business-rule errors -> 422; missing-reference errors -> 404
        code = (
            http_status.HTTP_422_UNPROCESSABLE_ENTITY
            if exc.code in {"SAME_TEAM", "INVALID_SALES_WINDOW", "SALES_AFTER_KICKOFF"}
            else http_status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=exc.message) from exc
    return MatchResponse.model_validate(match)


# ---------- Sections, seats, inventory ----------

@router.post(
    "/stadiums/{stadium_id}/sections",
    response_model=SectionResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_section(
    stadium_id: UUID,
    body: SectionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> SectionResponse:
    try:
        section = await admin_service.create_section(db, stadium_id, body)
    except admin_service.ServiceError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    return SectionResponse.model_validate(section)


@router.post(
    "/sections/{section_id}/seats",
    response_model=SeatBulkCreateResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_seats(
    section_id: UUID,
    body: SeatBulkCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> SeatBulkCreateResponse:
    try:
        count = await admin_service.create_seats_bulk(db, section_id, body)
    except admin_service.ServiceError as exc:
        code = (
            http_status.HTTP_404_NOT_FOUND
            if exc.code == "SECTION_NOT_FOUND"
            else http_status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=exc.message) from exc
    return SeatBulkCreateResponse(section_id=section_id, created=count)


@router.post(
    "/matches/{match_id}/inventory",
    response_model=InventoryGenerationResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def generate_inventory(
    match_id: UUID,
    body: MatchInventoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: RequireAdmin,
) -> InventoryGenerationResponse:
    try:
        rows_created, sections_priced = await admin_service.generate_match_inventory(
            db, match_id, body
        )
    except admin_service.ServiceError as exc:
        code = (
            http_status.HTTP_409_CONFLICT
            if exc.code == "DUPLICATE_INVENTORY"
            else http_status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=exc.message) from exc
    return InventoryGenerationResponse(
        match_id=match_id,
        rows_created=rows_created,
        sections_priced=sections_priced,
    )
