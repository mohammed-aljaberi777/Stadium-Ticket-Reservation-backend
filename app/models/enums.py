import enum


class UserRole(str, enum.Enum):
    """The three kinds of people who use the system."""

    FAN = "FAN"                    # books and views tickets
    ADMIN = "ADMIN"                # manages matches, seats, refunds
    GATE_SCANNER = "GATE_SCANNER"  # verifies QR codes at the stadium gate


class SectionCategory(str, enum.Enum):
    """What kind of seating a section offers."""

    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"
    VIP = "VIP"
    AWAY = "AWAY"


class SectionTier(str, enum.Enum):
    """Which ring/level of the stadium a section is on."""

    LOWER = "LOWER"
    MIDDLE = "MIDDLE"
    UPPER = "UPPER"


class Competition(str, enum.Enum):
    """Which competition a match belongs to."""

    BUNDESLIGA = "BUNDESLIGA"
    DFB_POKAL = "DFB_POKAL"
    CHAMPIONS_LEAGUE = "CHAMPIONS_LEAGUE"
    FRIENDLY = "FRIENDLY"


class MatchStatus(str, enum.Enum):
    """The lifecycle of a match."""

    SCHEDULED = "SCHEDULED"      # announced, no sales yet
    ON_SALE = "ON_SALE"          # tickets available
    SOLD_OUT = "SOLD_OUT"        # no tickets left
    IN_PROGRESS = "IN_PROGRESS"  # match is being played
    COMPLETED = "COMPLETED"      # match finished
    CANCELLED = "CANCELLED"      # match cancelled (triggers refunds)


class MatchSeatStatus(str, enum.Enum):
    """Durable state of a seat for a specific match. (LOCKED lives in Redis.)"""

    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"  # admin-held, not for public sale


class BookingStatus(str, enum.Enum):
    """The lifecycle of a booking (order)."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class TicketStatus(str, enum.Enum):
    """The lifecycle of a single ticket (entry pass)."""

    ISSUED = "ISSUED"
    USED = "USED"
    REVOKED = "REVOKED"
