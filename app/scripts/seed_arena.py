"""
Seed Allianz Arena with realistic sections, seats, and Klassiker pricing.

Run inside the api container:
    docker-compose exec api python -m app.scripts.seed_arena

This script is IDEMPOTENT:
- Sections that already exist (matched by stadium + name + tier) are skipped.
- Seats already in a section are kept (new ones added if missing).
- Inventory rows already created for (match, seat) are skipped.

So you can run it once, twice, or after partial manual setup — the end state
is always the same.
"""

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.enums import (
    MatchSeatStatus,
    SectionCategory,
    SectionTier,
)
from app.models.match import Match
from app.models.match_seat import MatchSeat
from app.models.seat import Seat
from app.models.section import Section
from app.models.stadium import Stadium

# ----------------------------------------------------------------------
# A scaled-down but structurally realistic Allianz Arena.
# Format: (name, category, tier, rows, seats_per_row, klassiker_price_eur)
# ----------------------------------------------------------------------
SECTIONS_BLUEPRINT: list[tuple[str, SectionCategory, SectionTier, int, int, str]] = [
    # --- LOWER tier (Unterrang) ---
    # Nordkurve + Südkurve (LOWER, STANDARD) are usually already created at €75.
    # The script skips them if found.
    ("Nordkurve",              SectionCategory.STANDARD, SectionTier.LOWER, 10, 20, "75.00"),
    ("Südkurve",               SectionCategory.STANDARD, SectionTier.LOWER, 10, 20, "75.00"),
    ("Westtribüne Unterrang",  SectionCategory.STANDARD, SectionTier.LOWER, 10, 25, "90.00"),
    ("Osttribüne Unterrang",   SectionCategory.STANDARD, SectionTier.LOWER, 10, 25, "90.00"),

    # --- MIDDLE tier (Mittelrang) — premium hospitality + VIP boxes ---
    ("Westtribüne Mittelrang", SectionCategory.PREMIUM,  SectionTier.MIDDLE, 8, 25, "150.00"),
    ("Osttribüne Mittelrang",  SectionCategory.PREMIUM,  SectionTier.MIDDLE, 8, 25, "150.00"),
    ("Logen West",             SectionCategory.VIP,      SectionTier.MIDDLE, 5, 10, "400.00"),
    ("Logen Ost",              SectionCategory.VIP,      SectionTier.MIDDLE, 5, 10, "400.00"),

    # --- UPPER tier (Oberrang) ---
    ("Nordkurve Oberrang",     SectionCategory.STANDARD, SectionTier.UPPER, 10, 20, "65.00"),
    ("Südkurve Oberrang",      SectionCategory.STANDARD, SectionTier.UPPER, 10, 20, "65.00"),
    ("Westtribüne Oberrang",   SectionCategory.STANDARD, SectionTier.UPPER, 10, 25, "80.00"),
    ("Osttribüne Oberrang",    SectionCategory.STANDARD, SectionTier.UPPER, 10, 25, "80.00"),

    # --- Away-fan corner (UEFA rule: capped, ~5% of capacity) ---
    ("Auswärtsblock",          SectionCategory.AWAY,     SectionTier.LOWER, 10, 20, "60.00"),
]


async def get_or_create_section(
    db: AsyncSession,
    stadium_id,
    name: str,
    category: SectionCategory,
    tier: SectionTier,
) -> tuple[Section, bool]:
    """Return (section, was_created). Idempotent on (stadium_id, name, tier)."""
    existing = await db.scalar(
        select(Section).where(
            Section.stadium_id == stadium_id,
            Section.name == name,
            Section.tier == tier,
        )
    )
    if existing is not None:
        return existing, False

    section = Section(
        stadium_id=stadium_id,
        name=name,
        category=category,
        tier=tier,
    )
    db.add(section)
    await db.flush()
    return section, True


async def ensure_seats(
    db: AsyncSession, section: Section, rows: int, seats_per_row: int
) -> int:
    """Create missing seats for this section. Returns the count of NEW seats added."""
    existing = (
        await db.scalars(select(Seat).where(Seat.section_id == section.id))
    ).all()
    existing_pairs = {(s.row_number, s.seat_number) for s in existing}

    to_add = []
    for row in range(1, rows + 1):
        for seat_num in range(1, seats_per_row + 1):
            key = (str(row), str(seat_num))
            if key not in existing_pairs:
                to_add.append(
                    Seat(
                        section_id=section.id,
                        row_number=str(row),
                        seat_number=str(seat_num),
                    )
                )

    if to_add:
        db.add_all(to_add)
        await db.flush()
    return len(to_add)


async def ensure_inventory(
    db: AsyncSession, match: Match, section: Section, price: Decimal
) -> int:
    """Create match_seats rows for any seats not yet priced for this match."""
    seat_ids = (
        await db.scalars(select(Seat.id).where(Seat.section_id == section.id))
    ).all()

    existing_ms = (
        await db.scalars(
            select(MatchSeat.seat_id).where(
                MatchSeat.match_id == match.id,
                MatchSeat.seat_id.in_(seat_ids),
            )
        )
    ).all()
    existing_set = set(existing_ms)

    to_add = [
        MatchSeat(
            match_id=match.id,
            seat_id=seat_id,
            price=price,
            status=MatchSeatStatus.AVAILABLE,
        )
        for seat_id in seat_ids
        if seat_id not in existing_set
    ]
    if to_add:
        db.add_all(to_add)
        await db.flush()
    return len(to_add)


async def seed(db: AsyncSession) -> None:
    print("=" * 70)
    print("Seeding Allianz Arena…")
    print("=" * 70)

    stadium = await db.scalar(select(Stadium).where(Stadium.name == "Allianz Arena"))
    if stadium is None:
        print("ERROR: Allianz Arena not found. Create it via the admin endpoint first.")
        return

    match = await db.scalar(select(Match).limit(1))
    if match is None:
        print("WARNING: no matches found — sections + seats will be created, but no inventory.")

    total_new_sections = 0
    total_new_seats = 0
    total_new_inventory = 0

    for name, category, tier, rows, seats_per_row, price in SECTIONS_BLUEPRINT:
        section, created = await get_or_create_section(
            db, stadium.id, name, category, tier
        )
        if created:
            total_new_sections += 1
            print(f"  + section: {name:<28} [{category.value:<8} / {tier.value:<6}]")
        else:
            print(f"  · section: {name:<28} [exists]")

        new_seats = await ensure_seats(db, section, rows, seats_per_row)
        total_new_seats += new_seats
        if new_seats:
            print(f"      + {new_seats} seats")

        if match is not None:
            new_inv = await ensure_inventory(db, match, section, Decimal(price))
            total_new_inventory += new_inv
            if new_inv:
                print(f"      + {new_inv} inventory rows  (€{price})")

    await db.commit()

    print()
    print("-" * 70)
    print(f"Done. New sections:   {total_new_sections}")
    print(f"      New seats:      {total_new_seats}")
    print(f"      New inventory:  {total_new_inventory}")
    print("-" * 70)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
