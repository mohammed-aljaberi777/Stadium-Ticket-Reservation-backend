#!/bin/sh
# Render Web Service entrypoint:
# 1. Apply any pending Alembic migrations (creates tables on first deploy,
#    no-op if already up to date — safe to run every boot).
# 2. Hand off (exec) to uvicorn so it's PID 1 and receives Render's signals.
set -e

echo "Running alembic migrations..."
alembic upgrade head

echo "Starting uvicorn on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
