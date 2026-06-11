# Bayern Tickets — Backend

> FastAPI backend for a stadium ticket reservation system inspired by FC Bayern München and the Allianz Arena.

[![Live API](https://img.shields.io/badge/API-live-success)](https://stadium-ticket-reservation-backend.onrender.com)
[![Docs](https://img.shields.io/badge/Swagger-docs-blue)](https://stadium-ticket-reservation-backend.onrender.com/docs)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com)

## Live deployment

| | URL |
|---|---|
| API root | https://stadium-ticket-reservation-backend.onrender.com |
| Interactive docs (Swagger) | https://stadium-ticket-reservation-backend.onrender.com/docs |
| Frontend (Vercel) | https://football-frontend-olive.vercel.app |

> Note: the backend runs on Render's free tier and sleeps after 15 minutes of inactivity. The first request after a sleep takes ~30 seconds to wake the container. Subsequent requests are instant.

## Features

- **JWT authentication** — short-lived access token (15 min) + refresh token (7 days), HMAC-SHA256
- **Mandatory 2FA TOTP** — every user must enroll in Google Authenticator before they can sign in
- **Role-based access** — FAN, ADMIN, GATE_SCANNER
- **Concurrency-safe seat holds** — Redis `SET NX EX` with a 5-minute TTL prevents double-booking
- **Transactional bookings** — Postgres `SELECT FOR UPDATE` guards the durable status flip at checkout
- **Auto-generated inventory** — creating a match automatically generates per-seat inventory rows with price derived from category and tier
- **Self-contained QR tickets** — each ticket carries a signed JWT inside its QR code; the gate scanner verifies the signature
- **Sales window enforcement** — holds rejected before `sales_open_at`
- **CORS configurable per environment** via `ALLOWED_ORIGINS`
- **Auto-applied migrations** — `start.sh` runs `alembic upgrade head` on every deploy

## Tech stack

- **Python 3.12** + **FastAPI 0.115** + **Uvicorn**
- **SQLAlchemy 2.0 (async)** + **asyncpg** (runtime) + **psycopg2** (Alembic)
- **PostgreSQL 16** + **Alembic** migrations
- **Redis 5.1 (redis-py)** for seat holds
- **Passlib + bcrypt** for password hashing
- **python-jose** for JWT
- **pyotp** for TOTP 2FA
- **qrcode + Pillow** for QR generation
- **Docker** — `python:3.12-slim` base image

## Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│   FAN / ADMIN /     │  HTTPS  │  FastAPI on Render  │
│   GATE_SCANNER      │ ◄─────► │   (Docker, EU)      │
└─────────────────────┘         └──────────┬──────────┘
                                            │
                          ┌─────────────────┴─────────────────┐
                          │                                   │
                          ▼                                   ▼
                ┌──────────────────┐               ┌──────────────────┐
                │  PostgreSQL 16   │               │   Redis (Valkey) │
                │   9 tables       │               │   Seat HOLDs     │
                │   (Render)       │               │   TTL = 5 min    │
                └──────────────────┘               └──────────────────┘
```

## Run locally

```bash
git clone https://github.com/mohammed-aljaberi777/Stadium-Ticket-Reservation-backend
cd Stadium-Ticket-Reservation-backend
cp .env.example .env       # then fill in JWT_SECRET_KEY etc.
docker-compose up --build
```

Once the containers are running:

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs

## Environment variables

| Name | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_DB` / `POSTGRES_PORT` | Database connection |
| `REDIS_HOST` / `REDIS_PORT` | Cache for seat holds |
| `JWT_SECRET_KEY` | 64-char random string (use `python -c "import secrets;print(secrets.token_urlsafe(64))"`) |
| `ENVIRONMENT` | `development` or `production` |
| `DEBUG` | `true` or `false` |
| `ALLOWED_ORIGINS` | Comma-separated CORS allow-list |

## API overview

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/auth/register` | — | Create account |
| POST | `/v1/auth/login` | — | Email + password |
| POST | `/v1/auth/2fa/setup` | Bearer | Generate TOTP QR |
| POST | `/v1/auth/2fa/verify` | Bearer | Submit 6-digit code |
| GET | `/v1/auth/me` | Bearer | Current user profile |
| GET | `/v1/matches` | — | List upcoming matches |
| GET | `/v1/matches/{id}/sections` | — | Section availability + prices |
| POST | `/v1/matches/{id}/holds` | Bearer | Reserve seats for 5 min |
| POST | `/v1/bookings` | Bearer | Confirm hold, issue ticket |
| GET | `/v1/tickets/me` | Bearer | List user's tickets |
| GET | `/v1/tickets/{id}/qr` | Bearer | Ticket QR as PNG |
| POST | `/v1/verify` | Bearer (GATE_SCANNER) | Verify QR token at gate |
| POST | `/v1/admin/teams` | Bearer (ADMIN) | Create team |
| POST | `/v1/admin/stadiums` | Bearer (ADMIN) | Create stadium |
| POST | `/v1/admin/matches` | Bearer (ADMIN) | Create match (auto-generates inventory) |

Full interactive documentation at the `/docs` endpoint.

## Project structure

```
app/
├── api/              # FastAPI routers (one per domain)
├── auth/             # JWT, password hashing, dependencies
├── core/             # config (Pydantic Settings)
├── db/               # SQLAlchemy session, Redis client
├── models/           # 9 SQLAlchemy models
├── schemas/          # Pydantic request/response shapes
├── services/         # business logic (admin, hold, booking)
└── scripts/          # seeding helpers
alembic/              # migrations
Dockerfile
docker-compose.yml
requirements.txt
start.sh              # production entrypoint
```

## Author

**Mohammed Al-Jaberi** — final-year project, 2026.

Frontend repository: [Stadium-Ticket-Reservation-frontend](https://github.com/mohammed-aljaberi777/Stadium-Ticket-Reservation-frontend)
