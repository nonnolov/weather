"""
Integration-test fixtures.

These fixtures connect to a REAL PostgreSQL database (configured via
DATABASE_URL env var) and run Alembic migrations before the test session.
They are intentionally separate from the unit-test conftest so that the
unit tests never require a live database.

Event-loop note
---------------
pytest-asyncio (asyncio_mode="auto") gives each test function its own event
loop. asyncpg connections are bound to the loop that created them, so the
engine and session fixtures must be function-scoped to avoid the
"Future attached to a different loop" RuntimeError.
Migrations are run once per session via a synchronous psycopg2 call.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _require_postgres_url() -> str:
    """
    Return the async PostgreSQL URL from the environment.
    Skips the entire integration suite if it is not set or points at SQLite.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url or "postgresql" not in url:
        pytest.skip(
            "Integration tests require DATABASE_URL pointing at PostgreSQL. "
            f"Got: {url!r}"
        )
    return url


def _require_sync_postgres_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC", "")
    if not url or "postgresql" not in url:
        pytest.skip(
            "Integration tests require DATABASE_URL_SYNC pointing at PostgreSQL. "
            f"Got: {url!r}"
        )
    return url


@pytest.fixture(scope="session", autouse=True)
def run_migrations() -> None:
    """
    Apply Alembic migrations once per test session using a synchronous
    psycopg2 connection (avoids event-loop lifetime issues).
    """
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    sync_url = _require_sync_postgres_url()
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    alembic_command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Each integration test gets its own async engine + session created in the
    test's own event loop (function scope). Changes are rolled back after the
    test to keep the database clean between tests.
    """
    async_url = _require_postgres_url()
    engine = create_async_engine(async_url, echo=False, pool_pre_ping=True)
    try:
        Session = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with Session() as session:
            yield session
            await session.rollback()
    finally:
        await engine.dispose()
