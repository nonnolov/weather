from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.metrics import EvaluationSample, calculate_metrics
from app.evaluation.service import evaluate_location_forecasts
from app.models.forecast import ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.observation import Observation


UTC = timezone.utc


def test_calculate_metrics_uses_forecast_minus_observation_and_skips_missing_values() -> None:
    retrieved_at = datetime(2024, 1, 1, tzinfo=UTC)
    samples = [
        EvaluationSample(
            "temperature_2m",
            retrieved_at,
            (retrieved_at + timedelta(hours=6)).replace(tzinfo=None),
            12.0,
            10.0,
        ),
        EvaluationSample("temperature_2m", retrieved_at, retrieved_at + timedelta(hours=6), 8.0, 10.0),
        EvaluationSample("temperature_2m", retrieved_at, retrieved_at + timedelta(hours=6), None, 10.0),
        EvaluationSample("temperature_2m", retrieved_at, retrieved_at + timedelta(hours=6), 10.0, None),
        EvaluationSample("wind_speed_10m", retrieved_at, retrieved_at + timedelta(hours=1), 7.0, 5.0),
        EvaluationSample("temperature_2m", retrieved_at, retrieved_at - timedelta(hours=1), 99.0, 0.0),
    ]

    metrics = calculate_metrics(reversed(samples))

    assert [(metric.variable, metric.horizon_hours) for metric in metrics] == [
        ("temperature_2m", 6.0),
        ("wind_speed_10m", 1.0),
    ]
    temperature, wind = metrics
    assert temperature.sample_count == 2
    assert temperature.mae == pytest.approx(2.0)
    assert temperature.rmse == pytest.approx(2.0)
    assert temperature.bias == pytest.approx(0.0)
    assert wind.bias == pytest.approx(2.0)


async def _location(db: AsyncSession, slug: str) -> Location:
    location = Location(
        name=slug,
        slug=slug,
        latitude=13.0,
        longitude=100.0,
        timezone="UTC",
        provider="open_meteo",
    )
    db.add(location)
    await db.flush()
    return location


@pytest.mark.asyncio
async def test_evaluation_matches_location_and_valid_time(db_session: AsyncSession) -> None:
    location = await _location(db_session, "evaluation-location")
    other_location = await _location(db_session, "other-location")
    retrieved_at = datetime(2024, 1, 1, tzinfo=UTC)
    valid_time = retrieved_at + timedelta(hours=3)

    first_run = ForecastRun(location_id=location.id, provider="open_meteo", retrieved_at=retrieved_at, forecast_days=1)
    second_run = ForecastRun(location_id=location.id, provider="open_meteo", retrieved_at=retrieved_at, forecast_days=1)
    other_run = ForecastRun(location_id=other_location.id, provider="open_meteo", retrieved_at=retrieved_at, forecast_days=1)
    db_session.add_all([first_run, second_run, other_run])
    await db_session.flush()
    db_session.add_all([
        HourlyForecast(forecast_run_id=first_run.id, valid_time=valid_time, temperature_2m=12.0),
        HourlyForecast(forecast_run_id=second_run.id, valid_time=valid_time, temperature_2m=8.0),
        HourlyForecast(forecast_run_id=first_run.id, valid_time=valid_time + timedelta(hours=1), temperature_2m=50.0),
        HourlyForecast(forecast_run_id=other_run.id, valid_time=valid_time, temperature_2m=100.0),
        Observation(location_id=location.id, observed_at=valid_time, source="fixture", temperature_2m=10.0),
        Observation(location_id=other_location.id, observed_at=valid_time, source="fixture", temperature_2m=0.0),
    ])
    await db_session.flush()

    metrics = await evaluate_location_forecasts(db_session, location.id)

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.variable == "temperature_2m"
    assert metric.horizon_hours == 3.0
    assert metric.sample_count == 2
    assert metric.mae == pytest.approx(2.0)
    assert metric.rmse == pytest.approx(2.0)
    assert metric.bias == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_evaluation_api_returns_empty_metrics_when_no_observations(client, db_session: AsyncSession) -> None:
    location = await _location(db_session, "evaluation-api")

    response = await client.get(f"/api/v1/forecast/{location.id}/evaluation")

    assert response.status_code == 200
    assert response.json() == {"location_id": location.id, "metrics": []}
