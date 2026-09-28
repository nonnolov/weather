import pytest
from datetime import datetime, timezone, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.location import Location
from app.models.forecast import ForecastRun, HourlyForecast, DailyForecast
from app.models.observation import Observation


async def _make_location(db: AsyncSession, slug: str = "test-loc") -> Location:
    loc = Location(
        name="Test City",
        slug=slug,
        latitude=35.0,
        longitude=139.0,
        timezone="UTC",
        provider="open_meteo",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest.mark.asyncio
async def test_location_model_persists(db_session: AsyncSession) -> None:
    loc = await _make_location(db_session, slug="persist-test")
    result = await db_session.execute(select(Location).where(Location.slug == "persist-test"))
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.name == "Test City"


@pytest.mark.asyncio
async def test_forecast_run_model(db_session: AsyncSession) -> None:
    loc = await _make_location(db_session, slug="run-test")
    run = ForecastRun(
        location_id=loc.id,
        provider="open_meteo",
        retrieved_at=datetime.now(timezone.utc),
        forecast_days=7,
    )
    db_session.add(run)
    await db_session.flush()
    assert run.id is not None


@pytest.mark.asyncio
async def test_hourly_forecast_model(db_session: AsyncSession) -> None:
    loc = await _make_location(db_session, slug="hourly-test")
    run = ForecastRun(
        location_id=loc.id,
        provider="open_meteo",
        retrieved_at=datetime.now(timezone.utc),
        forecast_days=1,
    )
    db_session.add(run)
    await db_session.flush()

    hourly = HourlyForecast(
        forecast_run_id=run.id,
        valid_time=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        temperature_2m=22.5,
        precipitation=0.0,
        weather_code=0,
    )
    db_session.add(hourly)
    await db_session.flush()
    assert hourly.id is not None
    assert hourly.temperature_2m == 22.5


@pytest.mark.asyncio
async def test_daily_forecast_model(db_session: AsyncSession) -> None:
    loc = await _make_location(db_session, slug="daily-test")
    run = ForecastRun(
        location_id=loc.id,
        provider="open_meteo",
        retrieved_at=datetime.now(timezone.utc),
        forecast_days=1,
    )
    db_session.add(run)
    await db_session.flush()

    daily = DailyForecast(
        forecast_run_id=run.id,
        forecast_date=date(2024, 6, 1),
        temperature_2m_max=28.0,
        temperature_2m_min=18.0,
        weather_code=0,
    )
    db_session.add(daily)
    await db_session.flush()
    assert daily.id is not None


@pytest.mark.asyncio
async def test_observation_model(db_session: AsyncSession) -> None:
    loc = await _make_location(db_session, slug="obs-test")
    obs = Observation(
        location_id=loc.id,
        observed_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        source="open_meteo_historical",
        temperature_2m=21.0,
        precipitation=0.5,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(obs)
    await db_session.flush()
    assert obs.id is not None
    assert obs.source == "open_meteo_historical"
