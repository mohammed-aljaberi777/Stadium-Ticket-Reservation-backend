"""How matches are shown to API clients."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Competition, MatchStatus
from app.schemas.stadium import StadiumResponse
from app.schemas.team import TeamResponse


class MatchCreate(BaseModel):
    """JSON body for POST /v1/admin/matches."""

    stadium_id: uuid.UUID
    home_team_id: uuid.UUID
    away_team_id: uuid.UUID
    competition: Competition
    kickoff_at: datetime
    sales_open_at: datetime
    sales_close_at: datetime
    max_tickets_per_user: int = Field(default=4, ge=1, le=20)


class MatchResponse(BaseModel):
    """A match with its team and stadium expanded as nested objects."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    home_team: TeamResponse
    away_team: TeamResponse
    stadium: StadiumResponse
    competition: Competition
    kickoff_at: datetime
    sales_open_at: datetime
    sales_close_at: datetime
    status: MatchStatus
    max_tickets_per_user: int


class MatchListResponse(BaseModel):
    """Paginated list response — standard {items, total, limit, offset} envelope."""

    items: list[MatchResponse]
    total: int
    limit: int
    offset: int
