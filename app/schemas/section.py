"""Section request and response shapes."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SectionCategory, SectionTier


class SectionCreate(BaseModel):
    """POST /v1/admin/stadiums/{id}/sections body."""

    name: str = Field(min_length=1, max_length=80)
    category: SectionCategory = SectionCategory.STANDARD
    tier: SectionTier


class SectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stadium_id: uuid.UUID
    name: str
    category: SectionCategory
    tier: SectionTier


class SectionSummary(BaseModel):
    """One section's per-match summary (used by GET /v1/matches/{id}/sections)."""

    section_id: uuid.UUID
    name: str
    category: SectionCategory
    tier: SectionTier
    available_seats: int
    total_seats: int
    min_price: Decimal
    max_price: Decimal


class SectionSummaryListResponse(BaseModel):
    items: list[SectionSummary]
