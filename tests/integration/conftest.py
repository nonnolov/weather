"""
Integration-test fixtures.

These fixtures connect to a REAL PostgreSQL database (configured via
DATABASE_URL env var) and run Alembic migrations before the test session.
They are intentionally separate from the unit-test conftest so that the
unit tests never require a live database.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
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


@pytest.fixture(scope="session")
def pg_database_url() -> str:
    return _require_postgres_url()


@pytest.fixture(scope="session")
def pg_database_url_sync() -> str:
    return _require_sync_postgres_url()


@pytest.fixture(scope="session")
def run_migrations(pg_database_url_sync: str) -> None:
    """Apply Alembic migrations once per test session."""
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", pg_database_url_sync)
    alembic_command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session")
async def pg_engine(pg_database_url: str, run_migrations: None):
    """Async engine connected to the real PostgreSQL database."""
    engine = create_async_engine(pg_database_url, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Each integration test gets its own session that is rolled back after
    the test, keeping the database clean between tests.
    """
    Session = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with Session() as session:
        yield session
        await session.rollback()
