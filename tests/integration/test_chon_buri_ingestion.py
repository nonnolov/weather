"""
Integration tests — real Open-Meteo API + real PostgreSQL.

These tests:
  1. Seed the four Chon Buri locations into the database.
  2. Call the real Open-Meteo API for each location.
  3. Persist the results via the existing ingestion service.
  4. Assert that ForecastRun, HourlyForecast, and DailyForecast records
     are created correctly.
  5. Assert that running ingestion twice creates two separate snapshots
     (immutability guarantee).

If Open-Meteo is unreachable the tests fail loudly with the real exception
— failures are never hidden or swallowed.

Run only in the CI integration job (requires DATABASE_URL pointing at
PostgreSQL and network access to api.open-meteo.com).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.service import ingest_forecast_for_location
from app.models.forecast import DailyForecast, ForecastRun, HourlyForecast
from app.models.location import Location
from app.seeds.locations import CHON_BURI_LOCATIONS, seed_locations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FORECAST_DAYS = 7
# Open-Meteo returns one row per hour for forecast_days days.
# Minimum expected: forecast_days * 24 (may be slightly more depending on
# the time of day the request is made, but never less).
MIN_HOURLY = FORECAST_DAYS * 24
MIN_DAILY = FORECAST_DAYS


async def _seed(session: AsyncSession) -> list[Location]:
    """Seed locations and return ORM objects."""
    await seed_locations(session)
    result = await session.execute(
        select(Location).where(Location.country_code == "TH").order_by(Location.slug)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_seed_creates_four_locations(pg_session: AsyncSession) -> None:
    """Seed must insert exactly the four Chon Buri locations."""
    locations = await _seed(pg_session)
    assert len(locations) == 4
    slugs = {loc.slug for loc in locations}
    assert slugs == {"chon-buri-city", "pattaya", "si-racha", "bang-lamung"}


@pytest.mark.integration
async def test_seed_is_idempotent(pg_session: AsyncSession) -> None:
    """Running seed twice must not create duplicate rows."""
    first = await seed_locations(pg_session)
    second = await seed_locations(pg_session)
    assert all(s == "created" for s in first.values())
    assert all(s == "skipped" for s in second.values())
    result = await pg_session.execute(
        select(Location).where(Location.country_code == "TH")
    )
    assert len(result.scalars().all()) == 4


@pytest.mark.integration
@pytest.mark.parametrize(
    "slug",
    ["chon-buri-city", "pattaya", "si-racha", "bang-lamung"],
)
async def test_real_ingestion_creates_forecast_run(
    pg_session: AsyncSession, slug: str
) -> None:
    """
    For each Chon Buri location, call the real Open-Meteo API and verify
    that a ForecastRun is persisted.
    """
    await seed_locations(pg_session)
    result = await pg_session.execute(
        select(Location).where(Location.slug == slug)
    )
    location = result.scalar_one()

    # — Real API call; will raise IngestionError loudly if Open-Meteo is down —
    run = await ingest_forecast_for_location(
        pg_session, location, forecast_days=FORECAST_DAYS
    )

    assert run.id is not None
    assert run.location_id == location.id
    assert run.provider == "open_meteo"
    assert run.forecast_days == FORECAST_DAYS
    assert run.retrieved_at is not None


@pytest.mark.integration
@pytest.mark.parametrize(
    "slug",
    ["chon-buri-city", "pattaya", "si-racha", "bang-lamung"],
)
async def test_real_ingestion_persists_hourly_records(
    pg_session: AsyncSession, slug: str
) -> None:
    """Hourly forecast records must be persisted for each location."""
    await seed_locations(pg_session)
    result = await pg_session.execute(
        select(Location).where(Location.slug == slug)
    )
    location = result.scalar_one()

    run = await ingest_forecast_for_location(
        pg_session, location, forecast_days=FORECAST_DAYS
    )

    hourly_result = await pg_session.execute(
        select(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
    )
    hourly = hourly_result.scalars().all()

    assert len(hourly) >= MIN_HOURLY, (
        f"{slug}: expected >= {MIN_HOURLY} hourly records, got {len(hourly)}"
    )
    # Spot-check: temperature must be a plausible tropical value
    temps = [h.temperature_2m for h in hourly if h.temperature_2m is not None]
    assert len(temps) > 0, f"{slug}: no temperature_2m values returned"
    assert all(15.0 <= t <= 45.0 for t in temps), (
        f"{slug}: temperature_2m values out of expected tropical range: "
        f"min={min(temps):.1f}, max={max(temps):.1f}"
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "slug",
    ["chon-buri-city", "pattaya", "si-racha", "bang-lamung"],
)
async def test_real_ingestion_persists_daily_records(
    pg_session: AsyncSession, slug: str
) -> None:
    """Daily forecast records must be persisted for each location."""
    await seed_locations(pg_session)
    result = await pg_session.execute(
        select(Location).where(Location.slug == slug)
    )
    location = result.scalar_one()

    run = await ingest_forecast_for_location(
        pg_session, location, forecast_days=FORECAST_DAYS
    )

    daily_result = await pg_session.execute(
        select(DailyForecast).where(DailyForecast.forecast_run_id == run.id)
    )
    daily = daily_result.scalars().all()

    assert len(daily) >= MIN_DAILY, (
        f"{slug}: expected >= {MIN_DAILY} daily records, got {len(daily)}"
    )
    # Spot-check: max temp must be warmer than min temp
    for day in daily:
        if day.temperature_2m_max is not None and day.temperature_2m_min is not None:
            assert day.temperature_2m_max >= day.temperature_2m_min, (
                f"{slug} {day.forecast_date}: max < min temperature"
            )


@pytest.mark.integration
async def test_separate_forecast_run_per_ingestion(pg_session: AsyncSession) -> None:
    """
    Running ingestion twice for the same location must create two separate
    ForecastRun rows — snapshots are never overwritten.
    """
    await seed_locations(pg_session)
    result = await pg_session.execute(
        select(Location).where(Location.slug == "chon-buri-city")
    )
    location = result.scalar_one()

    run1 = await ingest_forecast_for_location(
        pg_session, location, forecast_days=FORECAST_DAYS
    )
    run2 = await ingest_forecast_for_location(
        pg_session, location, forecast_days=FORECAST_DAYS
    )

    assert run1.id != run2.id, "Two ingestions must produce two distinct ForecastRun rows"

    all_runs_result = await pg_session.execute(
        select(ForecastRun).where(ForecastRun.location_id == location.id)
    )
    all_runs = all_runs_result.scalars().all()
    assert len(all_runs) == 2


@pytest.mark.integration
async def test_all_four_locations_ingested_successfully(
    pg_session: AsyncSession,
) -> None:
    """
    End-to-end: seed all four locations, ingest each one, verify all
    ForecastRun records exist with non-zero hourly and daily counts.
    """
    locations = await _seed(pg_session)
    assert len(locations) == 4

    summary: dict[str, dict] = {}
    for location in locations:
        run = await ingest_forecast_for_location(
            pg_session, location, forecast_days=FORECAST_DAYS
        )
        hourly_r = await pg_session.execute(
            select(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
        )
        daily_r = await pg_session.execute(
            select(DailyForecast).where(DailyForecast.forecast_run_id == run.id)
        )
        summary[location.slug] = {
            "run_id": run.id,
            "hourly": len(hourly_r.scalars().all()),
            "daily": len(daily_r.scalars().all()),
        }

    # Print a human-readable summary visible in CI logs
    print("\n\n=== Chon Buri Ingestion Summary ===")
    for slug, info in summary.items():
        print(
            f"  {slug:<20}  run_id={info['run_id']:>4}  "
            f"hourly={info['hourly']:>4}  daily={info['daily']:>2}"
        )
    print("==================================\n")

    for slug, info in summary.items():
        assert info["hourly"] >= MIN_HOURLY, (
            f"{slug}: only {info['hourly']} hourly records"
        )
        assert info["daily"] >= MIN_DAILY, (
            f"{slug}: only {info['daily']} daily records"
        )
