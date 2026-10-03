from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.metrics import EvaluationSample
from app.ml.bias_correction import fit_temperature_correction


UTC = timezone.utc


def _sample(hour: int, forecast: float, observed: float) -> EvaluationSample:
    retrieved = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour)
    return EvaluationSample("temperature_2m", retrieved, retrieved + timedelta(hours=1), forecast, observed)


def test_selects_linear_correction_only_when_later_mae_improves() -> None:
    correction = fit_temperature_correction([
        _sample(0, 10, 12), _sample(1, 20, 22), _sample(2, 30, 32),
        _sample(3, 40, 42), _sample(4, 50, 52),
    ])

    assert correction.selected is True
    assert correction.train_count == 4
    assert correction.test_count == 1
    assert correction.baseline_mae == pytest.approx(2.0)
    assert correction.corrected_mae == pytest.approx(0.0)
    assert correction.predict(60) == pytest.approx(62.0)


def test_held_out_future_sample_does_not_train_model() -> None:
    correction = fit_temperature_correction([
        _sample(0, 10, 12), _sample(1, 20, 22), _sample(2, 30, 32),
        _sample(3, 40, 42), _sample(4, 50, 1_000),
    ])

    assert correction.selected is True
    assert correction.train_count == 4
    assert correction.test_count == 1
    assert correction.intercept == pytest.approx(2.0)
    assert correction.slope == pytest.approx(1.0)
    assert correction.predict(60) == pytest.approx(62.0)


def test_too_few_samples_keeps_baseline() -> None:
    correction = fit_temperature_correction([_sample(0, 10, 12), _sample(1, 20, 22)])

    assert correction.selected is False
    assert correction.train_count == 0
    assert correction.test_count == 0


@pytest.mark.asyncio
async def test_corrected_forecast_api_uses_historical_training_only(
    client, db_session: AsyncSession
) -> None:
    from app.models.forecast import ForecastRun, HourlyForecast
    from app.models.location import Location
    from app.models.observation import Observation

    location = Location(
        name="ML API fixture",
        slug="ml-api-fixture",
        latitude=13.0,
        longitude=100.0,
        timezone="UTC",
        provider="open_meteo",
    )
    db_session.add(location)
    await db_session.flush()

    start = datetime(2024, 1, 1, tzinfo=UTC)
    for index in range(5):
        retrieved_at = start + timedelta(days=index)
        valid_time = retrieved_at + timedelta(hours=3)
        run = ForecastRun(
            location_id=location.id,
            provider="fixture",
            retrieved_at=retrieved_at,
            forecast_days=1,
        )
        db_session.add(run)
        await db_session.flush()
        db_session.add_all([
            HourlyForecast(
                forecast_run_id=run.id,
                valid_time=valid_time,
                temperature_2m=20.0 + index,
            ),
            Observation(
                location_id=location.id,
                observed_at=valid_time,
                source="fixture",
                temperature_2m=18.0 + index,
            ),
        ])

    current_retrieved_at = start + timedelta(days=10)
    current_run = ForecastRun(
        location_id=location.id,
        provider="fixture",
        retrieved_at=current_retrieved_at,
        forecast_days=1,
    )
    db_session.add(current_run)
    await db_session.flush()
    db_session.add(
        HourlyForecast(
            forecast_run_id=current_run.id,
            valid_time=current_retrieved_at + timedelta(hours=3),
            temperature_2m=42.0,
        )
    )
    await db_session.flush()

    response = await client.get(
        f"/api/v1/forecast/{location.id}/corrected?variable=temperature_2m"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["values"][0]["baseline_value"] == 42.0
    assert body["values"][0]["corrected_value"] == pytest.approx(40.0)
    assert body["values"][0]["model"] == "linear_regression"
    evaluation = body["evaluations"][0]
    assert evaluation["variable"] == "temperature_2m"
    assert evaluation["model"] == "linear_regression"
    assert evaluation["selected"] is True
    assert evaluation["train_count"] == 4
    assert evaluation["test_count"] == 1
