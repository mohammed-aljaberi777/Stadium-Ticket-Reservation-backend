"""Stadium request and response shapes."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class StadiumCreate(BaseModel):
    """JSON body for POST /v1/admin/stadiums."""

    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    capacity: int = Field(gt=0)


class StadiumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str
    capacity: int


class StadiumListResponse(BaseModel):
    items: list[StadiumResponse]
