import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import Competition, MatchStatus

if TYPE_CHECKING:
    from app.models.stadium import Stadium
    from app.models.team import Team


class Match(BaseModel):
    """A scheduled fixture at a stadium between two teams."""

    __tablename__ = "matches"

    stadium_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stadiums.id"))
    home_team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"))

    competition: Mapped[Competition] = mapped_column(
        SAEnum(Competition, name="competition")
    )
    kickoff_at: Mapped[datetime] = mapped_column()       # TIMESTAMPTZ via the type map
    sales_open_at: Mapped[datetime] = mapped_column()
    sales_close_at: Mapped[datetime] = mapped_column()
    status: Mapped[MatchStatus] = mapped_column(
        SAEnum(MatchStatus, name="match_status"),
        default=MatchStatus.SCHEDULED,
    )
    max_tickets_per_user: Mapped[int] = mapped_column(default=4)  # anti-scalping cap

    # Two foreign keys point to the SAME table (teams), so we must tell SQLAlchemy
    # which foreign key column each relationship should use.
    home_team: Mapped["Team"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team"] = relationship(foreign_keys=[away_team_id])
    stadium: Mapped["Stadium"] = relationship()
