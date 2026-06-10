"""
Business logic for Redis-backed seat holds.

This is the concurrency-critical service: it locks seats in Redis with
SET … NX EX, performs the anti-scalping cap check, and rolls back on
partial failure. Nothing here touches HTTP — the API layer translates.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus, MatchSeatStatus
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.models.ticket import Ticket

# How long a Redis hold lives. 5 minutes is the industry default.
HOLD_TTL_SECONDS = 300


# ---------- Key builders (single source of truth for naming) ----------

def hold_seat_key(match_id: UUID, match_seat_id: UUID) -> str:
    """Per-seat lock — set with NX EX to atomically claim a seat."""
    return f"hold:match:{match_id}:seat:{match_seat_id}"


def hold_group_key(hold_id: UUID) -> str:
    """Metadata for one hold (user, match, seats, expiry)."""
    return f"hold:group:{hold_id}"


def user_holds_key(user_id: UUID, match_id: UUID) -> str:
    """Set of the user's active hold_ids for a given match (anti-scalping)."""
    return f"holds:user:{user_id}:match:{match_id}"


# ---------- Errors ----------

class HoldError(Exception):
    """Raised when a hold operation fails. The API layer converts to HTTP."""

    def __init__(
        self, message: str, code: str, details: dict | None = None
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


# ---------- Helpers: count what the user already has ----------

async def _count_confirmed_tickets(
    db: AsyncSession, user_id: UUID, match_id: UUID
) -> int:
    """Tickets the user has already CONFIRMED for this match (Postgres)."""
    query = (
        select(func.count(Ticket.id))
        .join(Booking, Booking.id == Ticket.booking_id)
        .where(
            Booking.user_id == user_id,
            Booking.match_id == match_id,
            Booking.status == BookingStatus.CONFIRMED,
        )
    )
    return await db.scalar(query) or 0


async def _count_active_holds(
    redis_client: Redis, user_id: UUID, match_id: UUID
) -> int:
    """Seats currently held by user in this match (Redis)."""
    set_key = user_holds_key(user_id, match_id)
    hold_ids = await redis_client.smembers(set_key)
    if not hold_ids:
        return 0

    total = 0
    stale = []  # cleanup stale entries
    for hold_id_str in hold_ids:
        raw = await redis_client.get(hold_group_key(UUID(hold_id_str)))
        if raw is None:
            stale.append(hold_id_str)
            continue
        data = json.loads(raw)
        total += len(data.get("match_seat_ids", []))

    if stale:
        await redis_client.srem(set_key, *stale)
    return total


# ---------- The core: create_hold ----------

async def create_hold(
    db: AsyncSession,
    redis_client: Redis,
    *,
    user_id: UUID,
    match_id: UUID,
    match_seat_ids: list[UUID],
) -> dict:
    """
    Lock the given seats in Redis for HOLD_TTL_SECONDS.

    Steps:
      1. Verify the match exists.
      2. Verify the seats exist, belong to the match, and are AVAILABLE.
      3. Anti-scalping cap check (tickets + holds + new request <= max).
      4. Loop SET … NX EX per seat — rollback if any one fails.
      5. Store the group metadata + add to user's set.
    """
    # --- 1. Match exists? ---
    match = await db.get(Match, match_id)
    if match is None:
        raise HoldError("Match not found", code="MATCH_NOT_FOUND")

    # --- 1b. Sales window check ---
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if match.sales_open_at and now < match.sales_open_at:
        raise HoldError(
            "Ticket sales for this match have not opened yet.",
            code="SALES_NOT_OPEN",
            details={"sales_open_at": match.sales_open_at.isoformat()},
        )
    if match.sales_close_at and now > match.sales_close_at:
        raise HoldError(
            "Ticket sales for this match have closed.",
            code="SALES_CLOSED",
            details={"sales_close_at": match.sales_close_at.isoformat()},
        )

    # --- 2. All seats exist, belong to the match, and are AVAILABLE ---
    seats = (
        await db.scalars(
            select(MatchSeat).where(
                MatchSeat.id.in_(match_seat_ids),
                MatchSeat.match_id == match_id,
            )
        )
    ).all()

    if len(seats) != len(match_seat_ids):
        raise HoldError(
            "One or more seats not found in this match",
            code="SEATS_NOT_FOUND",
        )
    for seat in seats:
        if seat.status != MatchSeatStatus.AVAILABLE:
            raise HoldError(
                f"Seat {seat.id} is already booked",
                code="SEAT_NOT_AVAILABLE",
            )

    # --- 3. Anti-scalping cap check ---
    confirmed = await _count_confirmed_tickets(db, user_id, match_id)
    held = await _count_active_holds(redis_client, user_id, match_id)
    total_after = confirmed + held + len(match_seat_ids)
    if total_after > match.max_tickets_per_user:
        raise HoldError(
            (
                f"Holding these seats would exceed your limit of "
                f"{match.max_tickets_per_user} ticket(s) for this match"
            ),
            code="CAP_EXCEEDED",
            details={
                "max_tickets_per_user": match.max_tickets_per_user,
                "confirmed_tickets": confirmed,
                "active_holds": held,
                "requested": len(match_seat_ids),
            },
        )

    # --- 4. Atomic SET NX EX per seat, with rollback ---
    hold_id = uuid.uuid4()
    locked_keys: list[str] = []
    for ms_id in match_seat_ids:
        key = hold_seat_key(match_id, ms_id)
        # nx=True -> only set if not exists; ex=300 -> auto-expire
        ok = await redis_client.set(key, str(hold_id), nx=True, ex=HOLD_TTL_SECONDS)
        if ok:
            locked_keys.append(key)
        else:
            # Rollback: release whatever we already locked
            if locked_keys:
                await redis_client.delete(*locked_keys)
            raise HoldError(
                f"Seat {ms_id} is currently held by another user",
                code="SEAT_ALREADY_HELD",
                details={"match_seat_id": str(ms_id)},
            )

    # --- 5. Store group metadata + user's set ---
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=HOLD_TTL_SECONDS)
    group_data = {
        "hold_id": str(hold_id),
        "user_id": str(user_id),
        "match_id": str(match_id),
        "match_seat_ids": [str(x) for x in match_seat_ids],
        "expires_at": expires_at.isoformat(),
    }
    await redis_client.set(
        hold_group_key(hold_id),
        json.dumps(group_data),
        ex=HOLD_TTL_SECONDS,
    )

    set_key = user_holds_key(user_id, match_id)
    await redis_client.sadd(set_key, str(hold_id))
    await redis_client.expire(set_key, HOLD_TTL_SECONDS)

    return {
        "hold_id": hold_id,
        "match_id": match_id,
        "match_seat_ids": match_seat_ids,
        "expires_at": expires_at,
        "seconds_remaining": HOLD_TTL_SECONDS,
    }


# ---------- Release ----------

async def release_hold(
    redis_client: Redis,
    user_id: UUID,
    hold_id: UUID,
) -> None:
    """
    Release a hold early. Deletes all related Redis keys.

    Only the hold's owner can release it. If the hold doesn't exist or belongs
    to another user, we raise HOLD_NOT_FOUND — deliberately the same error
    in both cases, so we don't leak the existence of someone else's holds.
    """
    raw = await redis_client.get(hold_group_key(hold_id))
    if raw is None:
        raise HoldError("Hold not found or already expired", code="HOLD_NOT_FOUND")

    data = json.loads(raw)
    if data["user_id"] != str(user_id):
        raise HoldError("Hold not found or already expired", code="HOLD_NOT_FOUND")

    match_id = UUID(data["match_id"])
    match_seat_ids = [UUID(s) for s in data["match_seat_ids"]]

    # Delete every seat lock + the group metadata in one call
    keys = [hold_seat_key(match_id, ms) for ms in match_seat_ids]
    keys.append(hold_group_key(hold_id))
    await redis_client.delete(*keys)

    # Remove from the user's hold-set for this match
    await redis_client.srem(user_holds_key(user_id, match_id), str(hold_id))


# ---------- List my holds ----------

async def list_user_holds(
    db: AsyncSession,
    redis_client: Redis,
    user_id: UUID,
) -> list[dict]:
    """
    Return every active hold for this user, with seat info from Postgres.

    Uses SCAN (cursor-based, non-blocking) to find the user's hold-sets
    across all matches. For each hold, fetches metadata + seat details.
    """
    pattern = f"holds:user:{user_id}:match:*"
    out: list[dict] = []

    async for set_key in redis_client.scan_iter(match=pattern):
        hold_id_strs = await redis_client.smembers(set_key)
        stale: list[str] = []

        for hid_str in hold_id_strs:
            hold_id = UUID(hid_str)
            raw = await redis_client.get(hold_group_key(hold_id))
            if raw is None:
                # The group expired but the user-set still references it
                stale.append(hid_str)
                continue

            data = json.loads(raw)
            match_seat_ids = [UUID(s) for s in data["match_seat_ids"]]

            # Pull seat metadata in one JOIN
            q = (
                select(MatchSeat, Seat, Section)
                .join(Seat, Seat.id == MatchSeat.seat_id)
                .join(Section, Section.id == Seat.section_id)
                .where(MatchSeat.id.in_(match_seat_ids))
            )
            seat_rows = (await db.execute(q)).all()

            seats = [
                {
                    "match_seat_id": ms.id,
                    "section": section.name,
                    "row": seat.row_number,
                    "seat": seat.seat_number,
                    "price": ms.price,
                }
                for ms, seat, section in seat_rows
            ]

            ttl = await redis_client.ttl(hold_group_key(hold_id))
            out.append(
                {
                    "hold_id": hold_id,
                    "match_id": UUID(data["match_id"]),
                    "seats": seats,
                    "expires_at": datetime.fromisoformat(data["expires_at"]),
                    "seconds_remaining": max(0, ttl),
                }
            )

        # Clean up stale references in the user's hold-set
        if stale:
            await redis_client.srem(set_key, *stale)

    return out
