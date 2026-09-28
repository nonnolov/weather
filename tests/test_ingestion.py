import pytest
from datetime import datetime, timezone, date
from unittest.mock import patch, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.location import Location
from app.models.forecast import ForecastRun, HourlyForecast, DailyForecast
from app.ingestion.service import ingest_forecast_for_location, IngestionError
from app.providers.base import ProviderForecastResult, NormalizedHourlyForecast, NormalizedDailyForecast
from tests.conftest import FakeWeatherProvider


async def _make_location(db: AsyncSession) -> Location:
    location = Location(
        name="Tokyo",
        slug="tokyo-ingest-test",
        latitude=35.6762,
        longitude=139.6503,
        timezone="Asia/Tokyo",
        country_code="JP",
        provider="open_meteo",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(location)
    await db.flush()
    return location


@pytest.mark.asyncio
async def test_ingest_creates_forecast_run(db_session: AsyncSession) -> None:
    location = await _make_location(db_session)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        run = await ingest_forecast_for_location(db_session, location, forecast_days=7)

    assert run.id is not None
    assert run.location_id == location.id
    assert run.provider == "open_meteo"


@pytest.mark.asyncio
async def test_ingest_creates_hourly_records(db_session: AsyncSession) -> None:
    location = await _make_location(db_session)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        run = await ingest_forecast_for_location(db_session, location, forecast_days=7)

    result = await db_session.execute(
        select(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
    )
    hourly = result.scalars().all()
    assert len(hourly) == 24  # FakeWeatherProvider returns 24 hourly records


@pytest.mark.asyncio
async def test_ingest_creates_daily_records(db_session: AsyncSession) -> None:
    location = await _make_location(db_session)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        run = await ingest_forecast_for_location(db_session, location, forecast_days=7)

    result = await db_session.execute(
        select(DailyForecast).where(DailyForecast.forecast_run_id == run.id)
    )
    daily = result.scalars().all()
    assert len(daily) == 7


@pytest.mark.asyncio
async def test_ingest_unknown_provider_raises(db_session: AsyncSession) -> None:
    location = await _make_location(db_session)
    location.provider = "nonexistent"

    with pytest.raises(IngestionError, match="Unknown provider"):
        await ingest_forecast_for_location(db_session, location)


@pytest.mark.asyncio
async def test_ingest_provider_http_error_raises(db_session: AsyncSession) -> None:
    location = await _make_location(db_session)

    failing_provider = FakeWeatherProvider()
    failing_provider.fetch_forecast = AsyncMock(side_effect=Exception("HTTP 503"))

    with patch("app.ingestion.service.get_provider", return_value=failing_provider):
        with pytest.raises(IngestionError, match="Provider fetch failed"):
            await ingest_forecast_for_location(db_session, location)


@pytest.mark.asyncio
async def test_multiple_ingestions_create_separate_runs(db_session: AsyncSession) -> None:
    """Each ingestion must create a new immutable snapshot, never overwrite."""
    location = await _make_location(db_session)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        run1 = await ingest_forecast_for_location(db_session, location)
        run2 = await ingest_forecast_for_location(db_session, location)

    assert run1.id != run2.id

    result = await db_session.execute(
        select(ForecastRun).where(ForecastRun.location_id == location.id)
    )
    runs = result.scalars().all()
    assert len(runs) == 2
