# Import every model here so SQLAlchemy (and Alembic) can discover all tables
# by importing this single package.
from app.models.base import Base, BaseModel
from app.models.booking import Booking
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.models.stadium import Stadium
from app.models.team import Team
from app.models.ticket import Ticket
from app.models.user import User

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Team",
    "Stadium",
    "Section",
    "Seat",
    "Match",
    "MatchSeat",
    "Booking",
    "Ticket",
]
