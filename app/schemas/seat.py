"""Seat request and response shapes."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SeatBulkCreate(BaseModel):
    """
    POST /v1/admin/sections/{id}/seats body.

    Generates a grid of seats: for each row label in `rows`, creates seats
    numbered 1..seats_per_row. So `rows=["1","2","3"]` and `seats_per_row=20`
    creates 60 seats: rows 1, 2, 3, each with seats 1 through 20.
    """

    rows: list[str] = Field(min_length=1, max_length=200)
    seats_per_row: int = Field(ge=1, le=200)


class SeatBulkCreateResponse(BaseModel):
    section_id: uuid.UUID
    created: int


class SeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section_id: uuid.UUID
    row_number: str
    seat_number: str


# --- Match inventory generation ---


class SectionPrice(BaseModel):
    """One section's price within an inventory-generation request."""

    section_id: uuid.UUID
    price: Decimal = Field(gt=0, max_digits=8, decimal_places=2)


class MatchInventoryCreate(BaseModel):
    """POST /v1/admin/matches/{id}/inventory body."""

    section_prices: list[SectionPrice] = Field(min_length=1)


class InventoryGenerationResponse(BaseModel):
    match_id: uuid.UUID
    rows_created: int
    sections_priced: int
