# Database Schema (Entity Relationship Diagram)

This document describes the database design for the Stadium Ticket Reservation System.

The schema balances three competing concerns:

1. **Correctness** under heavy concurrent writes (booking commits).
2. **Speed** for read-heavy browse endpoints.
3. **Auditability** — financial records must survive forever and be traceable.

---

## Conventions

All tables follow these conventions:

- **Primary keys:** UUID (`gen_random_uuid()`)
- **Timestamps:** `TIMESTAMPTZ` for every time field
- **Money:** `NUMERIC(8,2)` for unit prices, `NUMERIC(10,2)` for totals — never `FLOAT`/`DOUBLE`
- **Finite-state columns:** PostgreSQL `ENUM` types
- **Naming:** `snake_case` for tables, columns, and JSON keys
- **Soft-delete:** never hard-delete; use status flags or `is_active`

---

## Schema overview

Nine tables in three clusters:

**People**
- `users` — fans, admins, gate scanners

**Physical world (static)**
- `teams` — football clubs
- `stadiums` — venues
- `sections` — areas within stadiums (Nordkurve, Südkurve, etc.)
- `seats` — physical seats

**Dynamic state**
- `matches` — scheduled fixtures
- `match_seats` — per-match inventory (price + status)
- `bookings` — fan orders
- `tickets` — entry passes with QR codes

---

## Relationship diagram

```
                ┌────────┐
                │ teams  │
                └────────┘
                  │   │
                  │   │ (home_team_id / away_team_id)
                  ▼   ▼
┌──────────┐   ┌──────────┐
│ stadiums │──▶│ matches  │
└──────────┘   └──────────┘
     │              │
     ▼              │
┌──────────┐        │
│ sections │        │
└──────────┘        │
     │              │
     ▼              ▼
┌────────┐    ┌──────────────┐
│ seats  │───▶│ match_seats  │   ← inventory (heart of the system)
└────────┘    └──────────────┘
                     ▲
                     │
                ┌─────────┐    ┌─────────┐
                │ tickets │◀──│bookings │◀── users
                └─────────┘    └─────────┘
```

---

## Cluster A — People

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `email` | VARCHAR(255) | Unique, indexed, lowercased before storage |
| `password_hash` | VARCHAR(255) | bcrypt hash (cost factor 12) |
| `full_name` | VARCHAR(120) | Display name |
| `role` | ENUM | `FAN`, `ADMIN`, `GATE_SCANNER` |
| `is_active` | BOOLEAN | Soft-disable accounts without deletion |
| `created_at` | TIMESTAMPTZ | Audit |
| `updated_at` | TIMESTAMPTZ | Audit |

**Indexes:** `UNIQUE(email)`, `INDEX(role)`.

---

## Cluster B — Physical world

### `teams`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | VARCHAR(120) | "FC Bayern München" |
| `short_name` | VARCHAR(10) | "FCB", "BVB", "S04" |
| `country` | VARCHAR(80) | "Germany" |
| `created_at` | TIMESTAMPTZ | |

### `stadiums`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | VARCHAR(120) | "Allianz Arena" |
| `city` | VARCHAR(80) | "München" |
| `capacity` | INT | ~75,000 |
| `created_at` | TIMESTAMPTZ | |

### `sections`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `stadium_id` | UUID | FK → `stadiums.id` |
| `name` | VARCHAR(80) | "Nordkurve", "Südtribüne Oberrang" |
| `category` | ENUM | `STANDARD`, `PREMIUM`, `VIP`, `AWAY` |
| `tier` | ENUM | `LOWER`, `MIDDLE`, `UPPER` |
| `created_at` | TIMESTAMPTZ | |

### `seats`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `section_id` | UUID | FK → `sections.id` |
| `row_number` | VARCHAR(8) | "12", "A" — text for flexibility |
| `seat_number` | VARCHAR(8) | "7" |
| `created_at` | TIMESTAMPTZ | |

**Constraints:** `UNIQUE(section_id, row_number, seat_number)`.

**Note:** No `status` column. A seat's availability depends on the match — that lives in `match_seats`.

---

## Cluster C — Dynamic state

### `matches`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `stadium_id` | UUID | FK → `stadiums.id` |
| `home_team_id` | UUID | FK → `teams.id` |
| `away_team_id` | UUID | FK → `teams.id` |
| `competition` | ENUM | `BUNDESLIGA`, `DFB_POKAL`, `CHAMPIONS_LEAGUE`, `FRIENDLY` |
| `kickoff_at` | TIMESTAMPTZ | When the match starts |
| `sales_open_at` | TIMESTAMPTZ | When ticket sales begin |
| `sales_close_at` | TIMESTAMPTZ | When sales close |
| `status` | ENUM | `SCHEDULED`, `ON_SALE`, `SOLD_OUT`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` |
| `max_tickets_per_user` | INT | Default 4 — anti-scalping cap |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### `match_seats` — the inventory

This is the heart of the system.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `match_id` | UUID | FK → `matches.id` |
| `seat_id` | UUID | FK → `seats.id` |
| `price` | NUMERIC(8,2) | Listed price for this seat at this match |
| `status` | ENUM | `AVAILABLE`, `BOOKED`, `BLOCKED` |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**Constraints:** `UNIQUE(match_id, seat_id)`.

**Important:** `LOCKED` is intentionally **not** in this enum. Temporary holds live in **Redis**, not Postgres.

### `bookings`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK → `users.id` |
| `match_id` | UUID | FK → `matches.id` |
| `reference_code` | VARCHAR(20) | Human-readable, unique (`FCB-2026-A4F2K9`) |
| `status` | ENUM | `PENDING`, `CONFIRMED`, `CANCELLED`, `REFUNDED` |
| `total_amount` | NUMERIC(10,2) | Sum of ticket prices in this booking |
| `client_ip` | INET | Audit / abuse forensics |
| `user_agent` | TEXT | Audit / abuse forensics |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### `tickets`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `booking_id` | UUID | FK → `bookings.id` |
| `match_seat_id` | UUID | FK → `match_seats.id` |
| `qr_token` | TEXT | Unique, signed JWT embedded in QR image |
| `price_paid` | NUMERIC(8,2) | Snapshot of price at booking time |
| `status` | ENUM | `ISSUED`, `USED`, `REVOKED` |
| `issued_at` | TIMESTAMPTZ | |
| `used_at` | TIMESTAMPTZ | NULL until scanned |
| `scanned_by_user_id` | UUID | FK → `users.id` — NULL until scanned |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**Constraint:** `UNIQUE(qr_token)`.

---

## The booking lifecycle, expressed in SQL

### 1. Browse

```sql
SELECT ms.id, s.row_number, s.seat_number, sec.name AS section, ms.price
FROM match_seats ms
JOIN seats s        ON s.id = ms.seat_id
JOIN sections sec   ON sec.id = s.section_id
WHERE ms.match_id = $1 AND ms.status = 'AVAILABLE';
```

### 2. Hold (Redis, not SQL)

```
SET hold:<match_id>:<seat_id> <hold_group_id> NX EX 300
```

### 3. Confirm (Postgres transaction)

```sql
BEGIN;

-- Re-verify availability under a lock (defense-in-depth)
SELECT id, status FROM match_seats
WHERE id = ANY($1) FOR UPDATE;

-- Anti-scalping cap re-check INSIDE the transaction
SELECT COUNT(*) FROM tickets t
JOIN bookings b ON b.id = t.booking_id
WHERE b.user_id = $user_id
  AND b.match_id = $match_id
  AND b.status = 'CONFIRMED';
-- If existing + requested > max_tickets_per_user → ROLLBACK

-- Create the order header
INSERT INTO bookings (id, user_id, match_id, reference_code,
                      status, total_amount, client_ip, user_agent)
VALUES (...);

-- Create one ticket per seat
INSERT INTO tickets (id, booking_id, match_seat_id, qr_token,
                     price_paid, status, issued_at)
VALUES (...);

-- Flip inventory to BOOKED
UPDATE match_seats
SET status = 'BOOKED', updated_at = NOW()
WHERE id = ANY($1);

COMMIT;
```

After commit: `DEL hold:<match_id>:<seat_id>` for each seat, and
`SET cooldown:booking:user:<user_id> 1 NX EX 30`.

### 4. Gate scan

```sql
UPDATE tickets
SET status = 'USED',
    used_at = NOW(),
    scanned_by_user_id = $scanner_id
WHERE id = $ticket_id AND status = 'ISSUED'
RETURNING *;
```

If a row is returned, entry approved. If `RETURNING` is empty, the ticket was already used, revoked, or never existed.

---

## Notes on key design choices

- **No `status` column on `seats`.** Availability is per-match. Putting status on the physical seat would force one global state across every match the seat is ever sold in.
- **`match_seats` is a normalized join table.** Each row is "this seat, in this match, at this price, with this status." Decouples the physical world from the dynamic world cleanly.
- **`LOCKED` lives in Redis, not Postgres.** Holding a Postgres transaction open for 5 minutes during user payment would exhaust the connection pool. Redis's native TTL handles auto-expiration without background workers.
- **`bookings` ↔ `tickets` are separate.** A booking is the order receipt (1 row, 1 total, 1 reference code); tickets are the entry passes (N rows, N QRs, N scan states). One booking = many tickets.
- **`price_paid` snapshot on tickets.** If prices change later, audit records must still show what the fan actually paid.
- **`scanned_by_user_id` on tickets.** Audit trail: which staff member scanned each ticket, useful for disputes.
- **Audit columns on `bookings` (`client_ip`, `user_agent`).** Don't enforce anything by themselves, but enable abuse investigation after the fact.

See [`DECISIONS.md`](DECISIONS.md) for the full reasoning behind every choice above.
