from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def _async_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(
    _async_database_url(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            from app.notifications.post_commit_preview import discard_forecast_previews
            discard_forecast_previews(session)
            await session.rollback()
            raise
        else:
            from app.notifications.post_commit_preview import run_forecast_previews
            await run_forecast_previews(session, AsyncSessionLocal)
