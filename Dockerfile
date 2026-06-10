# Small, secure base image with Python 3.12 pre-installed
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE: don't create .pyc files (cleaner containers)
# PYTHONUNBUFFERED: send logs straight to the terminal without buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Copy ONLY requirements first, so Docker can cache the pip-install layer.
# If app code changes but requirements don't, this layer is reused = faster builds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the application code and migration setup
COPY ./app ./app
COPY alembic.ini .
COPY ./alembic ./alembic

# Startup script (runs migrations then launches uvicorn).
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000

# Default command (docker-compose overrides this with --reload for dev)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
