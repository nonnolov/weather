"""
pytest fixtures shared across all tests.

Uses an in-memory SQLite database (via aiosqlite) so tests run without
a real PostgreSQL instance. The async engine is created fresh per test
session; each test gets its own transaction that is rolled back.
"""
import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone, date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.core.database import Base, get_db
from app.main import app
from app.providers.base import (
    BaseWeatherProvider,
    NormalizedHourlyForecast,
    NormalizedDailyForecast,
    ProviderForecastResult,
)

# ── In-memory SQLite engine (no PostgreSQL needed) ────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def engine():
    _engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Each test gets a fresh session; changes are rolled back after the test."""
    TestSession = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


# ── HTTP test client ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client wired to the test DB session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Fake weather provider ─────────────────────────────────────────────────────

class FakeWeatherProvider(BaseWeatherProvider):
    """Deterministic provider that returns canned data — no HTTP calls."""

    @property
    def name(self) -> str:
        return "open_meteo"

    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
        timezone: str = "UTC",
    ) -> ProviderForecastResult:
        # `timezone` parameter shadows datetime.timezone here too; use the
        # module-level import directly via the `timezone` name captured before
        # the method scope — simplest fix is to reference it via the module.
        _utc = __import__("datetime").timezone.utc
        hourly = [
            NormalizedHourlyForecast(
                valid_time=datetime(2024, 6, 1, h, 0, 0, tzinfo=_utc),
                temperature_2m=20.0 + h * 0.1,
                precipitation=0.0,
                weather_code=0,
            )
            for h in range(24)
        ]
        daily = [
            NormalizedDailyForecast(
                forecast_date=date(2024, 6, d),
                temperature_2m_max=25.0,
                temperature_2m_min=15.0,
                weather_code=0,
            )
            for d in range(1, forecast_days + 1)
        ]
        return ProviderForecastResult(
            provider=self.name,
            retrieved_at=datetime(2024, 6, 1, 0, 0, 0, tzinfo=_utc),
            model_run_time=None,
            hourly=hourly,
            daily=daily,
        )


@pytest.fixture
def fake_provider() -> FakeWeatherProvider:
    return FakeWeatherProvider()
