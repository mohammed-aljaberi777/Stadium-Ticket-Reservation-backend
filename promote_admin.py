"""
One-off script: promote a user to ADMIN or GATE_SCANNER role on the production DB.

Usage:
    python promote_admin.py <email> [role]

    role defaults to ADMIN. Valid roles: ADMIN, GATE_SCANNER, FAN.

Examples:
    DATABASE_URL="postgresql://..." python promote_admin.py mohammed@example.com
    DATABASE_URL="postgresql://..." python promote_admin.py scanner@example.com GATE_SCANNER
    DATABASE_URL="postgresql://..." python promote_admin.py oops@example.com FAN
"""
import os
import sys
import psycopg2

VALID_ROLES = {"ADMIN", "GATE_SCANNER", "FAN"}

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: Set DATABASE_URL env var to your Render EXTERNAL Postgres URL.")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python promote_admin.py <email> [role]")
    print("Valid roles: ADMIN (default), GATE_SCANNER, FAN")
    sys.exit(1)

email = sys.argv[1].lower().strip()
new_role = (sys.argv[2] if len(sys.argv) >= 3 else "ADMIN").upper().strip()

if new_role not in VALID_ROLES:
    print(f"ERROR: Invalid role '{new_role}'. Valid: {', '.join(VALID_ROLES)}")
    sys.exit(1)

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("SELECT id, email, role FROM users WHERE email = %s", (email,))
row = cur.fetchone()
if not row:
    print(f"No user found with email: {email}")
    print("Make sure that user registered first via the live site.")
    sys.exit(1)

user_id, user_email, current_role = row
print(f"Found user: {user_email} (current role: {current_role})")

if current_role == new_role:
    print(f"Already a {new_role}. Nothing to do.")
else:
    cur.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
    conn.commit()
    print(f"✅ Promoted {user_email} to {new_role}.")

cur.close()
conn.close()
