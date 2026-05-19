# Architectural Decisions

This document records the major architectural decisions for the **Stadium Ticket Reservation System** — a Bundesliga-inspired ticketing backend modeled loosely on the FC Bayern Munich / Allianz Arena experience.

Each entry follows the Architectural Decision Record (ADR) format used in production engineering teams: *what* was decided, *why* it was decided, and *what alternatives were considered*. Future contributors (and our future selves) can read this and quickly understand the reasoning, not just the result.

Decisions are organized by topic, in roughly the order they were made during Phase 1 planning.

---

## ADR-001: Technology Stack

**Status:** Accepted
**Date:** 2026-05-19

### Context
We need a backend stack capable of (a) handling heavy concurrent read traffic during ticket sales, (b) providing strict ACID guarantees for booking commits, (c) supporting sub-millisecond ephemeral locking, and (d) being easy to deploy for portfolio purposes.

### Decision
- **FastAPI** — Python async web framework
- **PostgreSQL** — primary durable datastore
- **Redis** — in-memory cache, ephemeral locks, rate limiting
- **SQLAlchemy + Alembic** — ORM and migrations
- **Pydantic** — request/response validation
- **Docker + docker-compose** — local development and deployment
- **GitHub Actions** — CI pipeline
- **Render** — deployment target

### Consequences
- Excellent async support; well-suited to I/O-bound ticket-booking workloads.
- Single-language stack (Python end-to-end) keeps cognitive load low.
- Pydantic + FastAPI gives free OpenAPI documentation at `/docs`.
- Trade-off: Python is slower than Go/Rust for CPU-bound work, but our workload is I/O-bound, so negligible.

### Alternatives considered
- **Node.js + Express/Fastify** — equally capable; Python chosen for ecosystem fit.
- **Go** — better raw performance; rejected as overkill for portfolio scope.

---

## ADR-002: Two-Layer Architecture (Redis + PostgreSQL)

**Status:** Accepted

### Context
Ticket booking has two distinct kinds of state:
- **Ephemeral holds** — last a few minutes, can be lost on crash, must be very fast.
- **Permanent bookings** — must be durable, transactional, and auditable.

Forcing both kinds of state into one store would force one of them to behave wrong.

### Decision
- **Redis** is the **fast layer** — temporary seat holds (with TTL), rate-limit counters, cooldown keys, and cached availability summaries.
- **PostgreSQL** is the **durable layer** — users, matches, inventory, bookings, tickets, refunds.

### Consequences
- Holds can have native TTL via `SET … EX`; no background-worker complexity.
- Booking confirmations run inside Postgres transactions for atomicity.
- Operational cost: two systems to manage instead of one.
- Resilience: if Redis goes down, in-progress holds are lost but no confirmed bookings are at risk.

### Alternatives considered
- **Postgres only**, using `SELECT … FOR UPDATE` for holds — rejected because holding a transaction open for the full 5-minute payment window would exhaust connection pools.
- **Redis only** — rejected because confirmed bookings would be lost on a Redis restart.

---

## ADR-003: Concurrency Strategy

**Status:** Accepted

### Context
Multiple users may attempt to book the same seat within the same millisecond, especially during the *Klassiker* sale opening. Without explicit protection, double-booking is guaranteed.

### Decision
Two cooperating mechanisms:
1. **Redis `SET key value NX EX 300`** for the 5-minute seat hold during seat selection. Atomic by Redis's single-threaded execution model.
2. **PostgreSQL transactions with `SELECT … FOR UPDATE`** for the permanent booking commit. The `match_seats` row is locked for the duration of the booking transaction.

### Consequences
- Race conditions between hold attempts are decided atomically by Redis (~0.5 ms).
- Race conditions between confirm-booking attempts are decided atomically by Postgres row locking.
- Defense-in-depth: even if a Redis hold leaks (e.g. TTL bug), the Postgres `FOR UPDATE` + re-check of `status = 'AVAILABLE'` catches it at commit time.

### Alternatives considered
- **Optimistic concurrency (version columns)** — simpler but produces high retry rates under heavy contention. Real ticketing systems prefer pessimistic locks for hot seats.
- **Application-level locks (`asyncio.Lock`)** — useless across multiple workers / processes / pods.

---

## ADR-004: Seat Availability Model

**Status:** Accepted

### Context
A seat's availability depends on the **match**, not on the seat alone. The same physical chair can be booked for one match and free for another.

### Decision
- A `match_seats` inventory table sits at the intersection of `matches` and `seats`.
- It stores per-match `price` and `status` (`AVAILABLE`, `BOOKED`, `BLOCKED`).
- The physical `seats` table holds **no** dynamic state.
- The `LOCKED` state is intentionally **not** in the inventory enum — temporary holds live only in Redis.

### Consequences
- Clean separation between physical structure and dynamic state.
- ~75,000 inventory rows per match; trivial for Postgres.
- Inventory generation is a one-time admin operation (`POST /v1/admin/matches/{id}/inventory`) per match.

### Alternatives considered
- **Status column on `seats` directly** — would force one global state across all matches. Rejected.
- **Implicit availability** (no status column, computed from active bookings) — requires expensive aggregations on every read. Rejected.

---

## ADR-005: Booking ↔ Ticket Separation

**Status:** Accepted

### Context
A real fan often books multiple seats in a single order (e.g., 4 tickets for a family). That order is one financial transaction; the entry passes are multiple physical artifacts, each with its own QR.

### Decision
- `bookings` — the order header (user, match, total amount, status, reference code).
- `tickets` — one row per seat, each with its own QR token, scan status, and price-paid snapshot.
- A booking has 1..N tickets.

### Consequences
- Matches the real-world mental model.
- Supports cancellation at the booking level (cancel all tickets together) and admin-level partial revocation.
- Adds JOINs in detail queries, but that cost is negligible at our scale.

### Alternatives considered
- **One row per ticket purchase, no booking concept** — loses the "order" abstraction, complicates totals and refunds.

---

## ADR-006: Authentication Strategy

**Status:** Accepted

### Context
We need stateless authentication for an API potentially consumed by web and mobile clients, and we want to limit the damage of token leaks.

### Decision
**JSON Web Tokens (JWT)** with the dual-token pattern:
- **Access token** — short-lived (~15 minutes), sent in `Authorization: Bearer <token>`.
- **Refresh token** — longer-lived (~7 days), used to obtain a new access token via `/v1/auth/refresh`.

Passwords are stored as **bcrypt** hashes (cost factor 12). Plain-text passwords are never persisted or logged.

### Consequences
- Stateless: no session lookup per request, horizontally scalable.
- Short access-token lifetime limits damage of leaks.
- Refresh tokens require careful storage on the client side (HttpOnly cookies recommended for browsers).

### Alternatives considered
- **Server-side sessions (Redis-backed)** — rejected for the per-request DB round-trip.
- **OAuth2 via external provider** — out of scope for portfolio version.

---

## ADR-007: Role-Based Access Control

**Status:** Accepted

### Context
Three fundamentally different actor types interact with the system: fans book tickets, admins manage the catalog, gate scanners verify QRs at the stadium.

### Decision
- Single `role` enum column on `users` with values `FAN`, `ADMIN`, `GATE_SCANNER`.
- One role per user.
- Authorization enforced at the endpoint level via FastAPI dependencies that read the JWT-decoded role.

### Consequences
- Simple to reason about and to test.
- A single user cannot simultaneously be a fan and an admin (acceptable: admins rarely also book).
- If multi-role becomes necessary, migration to a `user_roles` junction table is straightforward without breaking the API.

### Alternatives considered
- **Many-to-many roles** — overkill for current scope.
- **Permission-level RBAC** (e.g. `booking:create`, `match:edit`) — overkill; a future evolution if needed.

---

## ADR-008: Anti-Scalping Layered Defense

**Status:** Accepted

### Context
Scalping is a real problem in football ticketing. A single user (or bot) buying dozens of tickets damages fan experience and platform reputation. No single defense is sufficient; defense-in-depth is the industry standard.

### Decision
Four cooperating defenses:
1. **Per-match purchase cap** — `matches.max_tickets_per_user`, default 4, configurable per match (lower for high-demand fixtures like Bayern vs Real Madrid).
2. **Rate limiting** — sliding-window Redis counters on `POST /holds`, `POST /bookings`, `POST /auth/login`: 5/min per user, 10/min per IP.
3. **30-second cooldown** after a successful booking, enforced via Redis key with TTL.
4. **Personalized tickets** — the QR JWT carries `user_id` so resale to strangers is detectable at the gate.

The per-match cap is **re-verified inside the booking transaction**, after `SELECT … FOR UPDATE` locks are held, to close race-based bypasses.

### Consequences
- Mitigates the vast majority of brute-force and scripted abuse with low complexity.
- Does not stop sophisticated multi-account / device-fingerprinting attacks — acceptable for scope.
- Audit columns `client_ip` and `user_agent` on `bookings` enable post-hoc abuse investigation.

### Alternatives considered
- **CAPTCHA / Cloudflare Turnstile** — requires frontend integration; deferred to future scope.
- **ID verification at the gate** — operational complexity, out of scope.
- **Multi-account detection / ML fraud scoring** — enterprise-only, out of scope.

---

## ADR-009: API Conventions

**Status:** Accepted

### Context
Consistency across the API surface is a strong portfolio signal. Every URL, status code, and error format should look like the work of a single engineer who thought about the whole thing.

### Decision
- **REST-style** resource-oriented URLs (`/v1/matches/{id}`, not `/v1/getMatch`).
- **Versioned** with `/v1` prefix on every endpoint.
- **JSON in / JSON out**, `Content-Type: application/json`.
- **HTTP status codes used semantically** (200/201/204/400/401/403/404/409/422/429/500).
- **Consistent error envelope:** `{ "error": { "code": "...", "message": "...", "details": { ... } } }`.
- **Pagination envelope:** `{ "items": [...], "total": N, "limit": L, "offset": O }`.
- **Role-based documentation grouping** in the README: Public → Auth → Fan → Scanner → Admin.
- **OpenAPI / Swagger** auto-generated at `/docs` via FastAPI.

### Consequences
Reviewable, predictable, automatable. Clients (including the interactive Swagger UI) work without surprises.

---

## ADR-010: Data Types & Formats

**Status:** Accepted

### Context
Small type decisions made early prevent whole classes of bugs later (timezone drift, floating-point cent loss, enum typos).

### Decision
- **Primary keys:** UUID (`uuid_generate_v4()`) for every table.
- **Timestamps:** `TIMESTAMPTZ` always; never `TIMESTAMP` without timezone.
- **Money:** `NUMERIC(8,2)` for unit prices, `NUMERIC(10,2)` for totals. Never `FLOAT` or `DOUBLE`.
- **Enums:** PostgreSQL `ENUM` types for finite-state fields (statuses, roles, competitions).
- **Naming:** `snake_case` for tables, columns, and JSON keys (no `camelCase` switch at the boundary).

### Consequences
Eliminates entire bug categories at the database level. Slightly more verbose schemas; worth it.

---

## ADR-011: Git & Repository Workflow

**Status:** Accepted

### Context
A portfolio project's commit history is read by reviewers. It must reflect the discipline of a real engineer, not the chaos of a weekend hackathon.

### Decision
- **Polyrepo**: separate `bayern-tickets-backend` and `bayern-tickets-frontend` repositories. Different lifecycles, different deploy targets.
- **Branching strategy**: `main` is always deployable. Feature branches named `feature/<short-description>` merge in via Pull Requests, even when working solo.
- **Conventional Commits**: every commit subject begins with one of `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`.
- **Small, focused commits**: one logical change per commit.
- **Documentation-first**: `README.md`, `docs/ERD.md`, `docs/API.md`, and `docs/DECISIONS.md` are committed *before* any application code.

### Consequences
Readable history, easy reverts, automatable changelog generation, and strong signal of professional habit.

---

## ADR-012: Branding & Project Identity

**Status:** Accepted

### Context
The project is inspired by FC Bayern Munich and Allianz Arena, but it is a personal portfolio project and not an official product. We want the realism without the legal complications.

### Decision
- Bayern-inspired but **fictional** branding.
- German Bundesliga terminology (Nordkurve, Südkurve, Mitgliederverkauf, Logen, DFB-Pokal) is welcome for authenticity.
- Team names, club marks, and player likenesses are not used as official assets.
- Sample data (matches, opponents, prices) is illustrative.

### Consequences
- Authentic Bundesliga feel without trademark/licensing concerns.
- Avoids the "this looks like a class assignment" feel while staying legally safe.

---

## How this document evolves

This file is **append-only** in spirit. When a decision is superseded:
1. Add a new ADR with the new decision and `Status: Accepted`.
2. Mark the old ADR `Status: Superseded by ADR-NNN`.
3. Never delete old ADRs — the history of *why we changed our mind* is as valuable as the current decision.
