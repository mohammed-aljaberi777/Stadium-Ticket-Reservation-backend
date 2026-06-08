"""Gate verification request and response shapes."""

import uuid
from typing import Literal

from pydantic import BaseModel


class VerifyRequest(BaseModel):
    """POST /v1/verify body — the JWT decoded from the QR image."""

    qr_token: str


class VerifyTicketInfo(BaseModel):
    """Ticket info shown to the gate scanner on APPROVED."""

    id: uuid.UUID
    user_full_name: str          # so scanner can match against photo ID
    section: str
    row: str
    seat: str
    match: str                   # "FC Bayern München vs Borussia Dortmund"


class VerifyResponse(BaseModel):
    """Returned by POST /v1/verify — same shape for APPROVED or REJECTED."""

    result: Literal["APPROVED", "REJECTED"]
    ticket: VerifyTicketInfo | None = None       # populated only on APPROVED
    reason: str | None = None                    # populated only on REJECTED
    details: dict | None = None
