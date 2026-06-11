"""
One-off script: seed Allianz Arena with realistic sections, seats, and
generate per-match inventory for any matches already in that stadium.

Run after seed_stadium.py + creating matches via the admin UI.

Usage:
    DATABASE_URL="postgresql://..." python seed_arena_simple.py

Idempotent — safe to run multiple times.
"""
import os
import sys
import uuid
import psycopg2

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: Set DATABASE_URL env var to your Render EXTERNAL Postgres URL.")
    sys.exit(1)

STADIUM_NAME = "Allianz Arena"

# (name, category, tier, rows, seats_per_row, price_eur)
SECTIONS = [
    # LOWER tier
    ("Nordkurve",              "STANDARD", "LOWER", 8, 15, "75.00"),
    ("Suedkurve",              "STANDARD", "LOWER", 8, 15, "75.00"),
    ("Westtribuene Unterrang", "STANDARD", "LOWER", 8, 18, "90.00"),
    ("Osttribuene Unterrang",  "STANDARD", "LOWER", 8, 18, "90.00"),
    # MIDDLE tier
    ("Westtribuene Mittelrang","PREMIUM",  "MIDDLE", 6, 18, "150.00"),
    ("Osttribuene Mittelrang", "PREMIUM",  "MIDDLE", 6, 18, "150.00"),
    ("Logen West",             "VIP",      "MIDDLE", 4, 8,  "400.00"),
    ("Logen Ost",              "VIP",      "MIDDLE", 4, 8,  "400.00"),
    # UPPER tier
    ("Nordkurve Oberrang",     "STANDARD", "UPPER",  8, 15, "65.00"),
    ("Suedkurve Oberrang",     "STANDARD", "UPPER",  8, 15, "65.00"),
    ("Westtribuene Oberrang",  "STANDARD", "UPPER",  8, 18, "80.00"),
    ("Osttribuene Oberrang",   "STANDARD", "UPPER",  8, 18, "80.00"),
    # AWAY block
    ("Auswaertsblock",         "AWAY",     "LOWER",  8, 15, "60.00"),
]


conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# --- 1. Find the stadium ---
cur.execute("SELECT id FROM stadiums WHERE name = %s", (STADIUM_NAME,))
row = cur.fetchone()
if not row:
    print(f"ERROR: Stadium '{STADIUM_NAME}' not found. Run seed_stadium.py first.")
    sys.exit(1)
stadium_id = row[0]
print(f"Found stadium: {STADIUM_NAME} (id={stadium_id})\n")

# --- 2. Create sections + seats ---
total_seats_created = 0
section_seat_prices = {}  # section_id -> price

for name, category, tier, num_rows, seats_per_row, price in SECTIONS:
    # Skip if section already exists
    cur.execute(
        "SELECT id FROM sections WHERE stadium_id = %s AND name = %s",
        (stadium_id, name),
    )
    existing = cur.fetchone()
    if existing:
        section_id = existing[0]
        print(f"  Section '{name}' already exists, skipping creation.")
    else:
        section_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO sections (id, stadium_id, name, category, tier, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (section_id, stadium_id, name, category, tier),
        )
        print(f"  Created section '{name}' ({category}/{tier})")

    section_seat_prices[section_id] = price

    # Add seats (skip if they already exist)
    for r in range(1, num_rows + 1):
        for s in range(1, seats_per_row + 1):
            cur.execute(
                """
                SELECT 1 FROM seats
                WHERE section_id = %s AND row_number = %s AND seat_number = %s
                """,
                (section_id, str(r), str(s)),
            )
            if cur.fetchone():
                continue
            seat_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO seats (id, section_id, row_number, seat_number, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                (seat_id, section_id, str(r), str(s)),
            )
            total_seats_created += 1

conn.commit()
print(f"\n  Created {total_seats_created} new seats.")

# --- 3. Generate match_seat inventory for existing matches at this stadium ---
cur.execute("SELECT id FROM matches WHERE stadium_id = %s", (stadium_id,))
match_ids = [r[0] for r in cur.fetchall()]
print(f"\nFound {len(match_ids)} matches at this stadium.")

if not match_ids:
    print("  No matches yet. Inventory will auto-generate when you create one.")
else:
    # Pull all seats for this stadium + their section's price
    cur.execute(
        """
        SELECT seats.id, sections.id AS section_id
        FROM seats
        JOIN sections ON sections.id = seats.section_id
        WHERE sections.stadium_id = %s
        """,
        (stadium_id,),
    )
    all_seats = cur.fetchall()  # list of (seat_id, section_id)

    inventory_created = 0
    for match_id in match_ids:
        for seat_id, section_id in all_seats:
            price = section_seat_prices.get(section_id, "75.00")
            cur.execute(
                """
                INSERT INTO match_seats (id, match_id, seat_id, price, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'AVAILABLE', NOW(), NOW())
                ON CONFLICT (match_id, seat_id) DO NOTHING
                """,
                (str(uuid.uuid4()), match_id, seat_id, price),
            )
            if cur.rowcount > 0:
                inventory_created += 1
    conn.commit()
    print(f"  Created {inventory_created} match-seat inventory rows.")

# Summary
cur.execute("SELECT COUNT(*) FROM sections WHERE stadium_id = %s", (stadium_id,))
n_sections = cur.fetchone()[0]
cur.execute(
    "SELECT COUNT(*) FROM seats JOIN sections ON sections.id = seats.section_id WHERE sections.stadium_id = %s",
    (stadium_id,),
)
n_seats = cur.fetchone()[0]
cur.execute(
    "SELECT COUNT(*) FROM match_seats WHERE match_id = ANY(%s)",
    (match_ids,),
)
n_inventory = cur.fetchone()[0] if match_ids else 0

print(f"\n=== Summary ===")
print(f"  Sections: {n_sections}")
print(f"  Seats:    {n_seats}")
print(f"  Inventory rows: {n_inventory}")
print("\nDone! Refresh the match page in your browser.")

cur.close()
conn.close()
