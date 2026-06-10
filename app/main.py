from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, bookings, health, holds, matches, tickets, totp, verify
from app.core.config import settings
from app.db.redis import redis_client
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown hook."""
    # --- startup --- (nothing special needed yet)
    yield
    # --- shutdown --- cleanly release connection pools
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# --- CORS: allow the frontend dev server AND deployed Vercel URL ---
# ALLOWED_ORIGINS env var = comma-separated list of origins.
# Defaults cover local dev; production sets it to include the Vercel URL.
import os

_default_origins = "http://localhost:5173,http://localhost:3000"
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(admin.router)
app.include_router(holds.router)
app.include_router(bookings.router)
app.include_router(tickets.router)
app.include_router(verify.router)
app.include_router(totp.router)


@app.get("/")
async def root() -> dict:
    """Root endpoint — a friendly pointer to the interactive docs."""
    return {"message": f"{settings.APP_NAME} API", "docs": "/docs"}
