"""Team request and response shapes."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class TeamCreate(BaseModel):
    """JSON body for POST /v1/admin/teams."""

    name: str = Field(min_length=1, max_length=120)
    short_name: str = Field(min_length=1, max_length=10)
    country: str = Field(min_length=1, max_length=80)
    # No max length — accepts both URLs and base64 data URIs for uploaded images
    logo_url: str | None = None


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    short_name: str
    country: str
    logo_url: str | None = None


class TeamListResponse(BaseModel):
    items: list[TeamResponse]
