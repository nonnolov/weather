"""Database-facing local temperature bias correction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.metrics import EvaluationSample
from app.ml.bias_correction import TemperatureCorrection, fit_temperature_correction
from app.models.forecast import ForecastRun, HourlyForecast
from app.models.observation import Observation


@dataclass(frozen=True)
class CorrectedHourlyValue:
    valid_time: datetime
    variable: str
    horizon_hours: float
    baseline_value: float
    corrected_value: float
    model: str | None
    applied: bool


@dataclass(frozen=True)
class CorrectedForecast:
    forecast_run_id: int
    location_id: int
    values: list[CorrectedHourlyValue]
    evaluations: list[TemperatureCorrection]


async def correct_forecast_run(
    db: AsyncSession, run: ForecastRun, variables: tuple[str, ...] = ("temperature_2m",)
) -> CorrectedForecast:
    """Correct values from snapshots observed before this run existed."""
    correction = await fit_location_temperature_correction(db, run.location_id, run.retrieved_at)
    values: list[CorrectedHourlyValue] = []
    for forecast in sorted(run.hourly_forecasts, key=lambda item: _as_utc(item.valid_time)):
        horizon = (_as_utc(forecast.valid_time) - _as_utc(run.retrieved_at)).total_seconds()
        if horizon < 0:
            continue
        for variable in variables:
            if variable != "temperature_2m" or not _is_finite(forecast.temperature_2m):
                continue
            baseline = float(forecast.temperature_2m)
            values.append(CorrectedHourlyValue(
                valid_time=forecast.valid_time, variable=variable, horizon_hours=horizon / 3600,
                baseline_value=baseline, corrected_value=float(correction.predict(baseline)),
                model="linear_regression" if correction.selected else None, applied=correction.selected,
            ))
    return CorrectedForecast(run.id, run.location_id, values, [correction])


async def fit_location_temperature_correction(
    db: AsyncSession, location_id: int, cutoff: datetime | None = None
) -> TemperatureCorrection:
    """Use matched snapshots completed before cutoff. No future target leakage."""
    statement = (
        select(HourlyForecast, ForecastRun, Observation)
        .join(ForecastRun, HourlyForecast.forecast_run_id == ForecastRun.id)
        .join(Observation, and_(Observation.location_id == ForecastRun.location_id,
                                Observation.observed_at == HourlyForecast.valid_time))
        .where(ForecastRun.location_id == location_id)
        .where(HourlyForecast.valid_time >= ForecastRun.retrieved_at)
        .order_by(HourlyForecast.valid_time, ForecastRun.retrieved_at, ForecastRun.id)
    )
    if cutoff is not None:
        statement = statement.where(Observation.observed_at < cutoff).where(ForecastRun.retrieved_at < cutoff)
    result = await db.execute(statement)
    return fit_temperature_correction(
        EvaluationSample("temperature_2m", run.retrieved_at, forecast.valid_time,
                         forecast.temperature_2m, observation.temperature_2m)
        for forecast, run, observation in result.tuples()
    )


def _is_finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
