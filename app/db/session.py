from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# The engine owns a pool of connections to PostgreSQL.
# It is created once and shared across the whole application.
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,    # log every SQL statement while DEBUG is on
    pool_pre_ping=True,     # verify a connection is alive before handing it out
)

# A factory that produces fresh AsyncSession objects bound to the engine.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep objects usable after commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield one database session per request, then close it."""
    async with AsyncSessionLocal() as session:
        yield session
