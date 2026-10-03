from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.service import evaluate_location_forecasts
from app.ingestion.service import (
    IngestionError,
    ingest_forecast_for_location,
    ingest_observations_for_location,
    ingest_seed_observations,
)
from app.models.location import Location
from app.models.observation import Observation
from app.providers.base import ProviderObservationResult
from app.seeds.locations import seed_locations
from tests.conftest import FakeWeatherProvider


async def _location(db: AsyncSession, slug: str) -> Location:
    location = Location(
        name=slug, slug=slug, latitude=13.0, longitude=100.0,
        timezone="Asia/Bangkok", provider="open_meteo",
    )
    db.add(location)
    await db.flush()
    return location


@pytest.mark.asyncio
async def test_default_observation_end_date_uses_thailand_date(db_session: AsyncSession, monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2024, 6, 2, 0, 30, tzinfo=tz)

    provider = MagicMock()
    provider.name = "open_meteo"
    provider.fetch_observations = AsyncMock(
        return_value=ProviderObservationResult(provider="open_meteo", observations=[])
    )
    thailand_tz = timezone(timedelta(hours=7))
    monkeypatch.setattr("app.ingestion.service.datetime", FixedDateTime)
    monkeypatch.setattr("app.ingestion.service.ZoneInfo", lambda key: thailand_tz)

    location = await _location(db_session, "observation-thailand-date")
    with patch("app.ingestion.service.get_provider", return_value=provider):
        await ingest_observations_for_location(db_session, location)

    request = provider.fetch_observations.await_args.kwargs
    assert request["start_date"] == date(2024, 6, 1)
    assert request["end_date"] == date(2024, 6, 1)


@pytest.mark.asyncio
async def test_observation_ingestion_persists_evaluation_fields(db_session: AsyncSession) -> None:
    location = await _location(db_session, "observation-ingest")
    with patch("app.ingestion.service.get_provider", return_value=FakeWeatherProvider()):
        created = await ingest_observations_for_location(
            db_session, location, date(2024, 6, 1), date(2024, 6, 1)
        )

    records = (await db_session.execute(select(Observation).where(Observation.location_id == location.id))).scalars().all()
    assert created == 2
    assert len(records) == 2
    assert records[0].source == "open_meteo_historical"
    assert records[0].temperature_2m == 20.0
    assert records[0].precipitation == 0.1
    assert records[0].weather_code == 61
    assert records[0].wind_speed_10m == 7.0


@pytest.mark.asyncio
async def test_observation_ingestion_is_idempotent_and_keeps_other_locations(db_session: AsyncSession) -> None:
    location = await _location(db_session, "observation-idempotent")
    other = await _location(db_session, "observation-other")
    other_record = Observation(
        location_id=other.id,
        observed_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        source="fixture", temperature_2m=99.0,
    )
    db_session.add(other_record)
    await db_session.flush()

    with patch("app.ingestion.service.get_provider", return_value=FakeWeatherProvider()):
        first = await ingest_observations_for_location(db_session, location, date(2024, 6, 1), date(2024, 6, 1))
        second = await ingest_observations_for_location(db_session, location, date(2024, 6, 1), date(2024, 6, 1))

    assert (first, second) == (2, 0)
    assert await db_session.get(Observation, other_record.id) is other_record
    assert other_record.temperature_2m == 99.0


@pytest.mark.asyncio
async def test_observation_ingestion_deduplicates_provider_timestamps(db_session: AsyncSession) -> None:
    location = await _location(db_session, "observation-provider-duplicates")
    fake = FakeWeatherProvider()
    result = await fake.fetch_observations(13.0, 100.0, date(2024, 6, 1), date(2024, 6, 1))
    fake.fetch_observations = AsyncMock(
        return_value=ProviderObservationResult(
            provider=fake.name,
            observations=[result.observations[0], result.observations[0]],
        )
    )

    with patch("app.ingestion.service.get_provider", return_value=fake):
        created = await ingest_observations_for_location(
            db_session, location, date(2024, 6, 1), date(2024, 6, 1)
        )

    assert created == 1


@pytest.mark.asyncio
async def test_observation_ingestion_rejects_invalid_date_range(db_session: AsyncSession) -> None:
    location = await _location(db_session, "observation-invalid-range")

    with pytest.raises(IngestionError, match="start_date"):
        await ingest_observations_for_location(
            db_session, location, date(2024, 6, 2), date(2024, 6, 1)
        )


@pytest.mark.asyncio
async def test_ingested_observations_feed_evaluation(db_session: AsyncSession) -> None:
    location = await _location(db_session, "observation-evaluation")
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        await ingest_forecast_for_location(db_session, location, forecast_days=1)
        await ingest_observations_for_location(
            db_session, location, date(2024, 6, 1), date(2024, 6, 1)
        )

    metrics = await evaluate_location_forecasts(db_session, location.id)

    temperature_metrics = [metric for metric in metrics if metric.variable == "temperature_2m"]
    assert [(metric.horizon_hours, metric.sample_count) for metric in temperature_metrics] == [
        (0.0, 1),
        (1.0, 1),
    ]


@pytest.mark.asyncio
async def test_seed_observation_ingestion_targets_four_seed_locations(db_session: AsyncSession) -> None:
    await seed_locations(db_session)
    with patch("app.ingestion.service.get_provider", return_value=FakeWeatherProvider()):
        counts = await ingest_seed_observations(db_session, date(2024, 6, 1), date(2024, 6, 1))

    assert counts == {
        "chon-buri-city": 2,
        "pattaya": 2,
        "si-racha": 2,
        "bang-lamung": 2,
    }
