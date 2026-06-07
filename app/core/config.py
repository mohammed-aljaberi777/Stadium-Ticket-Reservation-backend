from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application ---
    APP_NAME: str = "Stadium Ticket Reservation"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # --- PostgreSQL (required — no defaults, so misconfiguration fails loudly) ---
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # --- Redis ---
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # --- Security / JWT ---
    JWT_SECRET_KEY: str                          # required — must be set in .env
    JWT_ALGORITHM: str = "HS256"                 # HMAC-SHA256, the standard choice
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15        # short-lived: limits damage if leaked
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7           # longer-lived: silent refresh on the frontend

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string (uses the asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous connection string (psycopg2) — used only by Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        """Redis connection string (database index 0)."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is read only once."""
    return Settings()


settings = get_settings()
