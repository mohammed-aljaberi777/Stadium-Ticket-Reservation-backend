"""
One-off script: insert a stadium directly into the production DB.

Usage (with the EXTERNAL Database URL from Render):
    DATABASE_URL="postgresql://..." python seed_stadium.py

Creates the Allianz Arena if it doesn't already exist.
"""
import os
import sys
import uuid
import psycopg2

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: Set DATABASE_URL env var to your Render EXTERNAL Postgres URL.")
    sys.exit(1)

STADIUM = {
    "name": "Allianz Arena",
    "city": "München",
    "capacity": 75024,
}

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Skip if already exists
cur.execute("SELECT id FROM stadiums WHERE name = %s", (STADIUM["name"],))
existing = cur.fetchone()
if existing:
    print(f"Stadium '{STADIUM['name']}' already exists with id={existing[0]}. Skipping.")
else:
    new_id = uuid.uuid4()
    cur.execute(
        """
        INSERT INTO stadiums (id, name, city, capacity, created_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        """,
        (str(new_id), STADIUM["name"], STADIUM["city"], STADIUM["capacity"]),
    )
    conn.commit()
    print(f"Created stadium '{STADIUM['name']}' with id={new_id}.")

# Show all stadiums for confirmation
cur.execute("SELECT id, name, city, capacity FROM stadiums")
print("\nAll stadiums in DB:")
for row in cur.fetchall():
    print(f"  - {row[1]} ({row[2]}, capacity: {row[3]})")

cur.close()
conn.close()
