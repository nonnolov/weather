"""Database matching for historical forecast evaluation."""
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.metrics import EvaluationSample, ForecastMetric, calculate_metrics
from app.models.forecast import ForecastRun, HourlyForecast
from app.models.observation import Observation


# Fields available as continuous values in both hourly forecasts and observations.
COMPARABLE_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "dewpoint_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "snowfall",
    "cloud_cover",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "visibility",
    "uv_index",
)


async def evaluate_location_forecasts(
    db: AsyncSession, location_id: int
) -> list[ForecastMetric]:
    """Evaluate all stored hourly forecasts for a location with matching observations."""
    result = await db.execute(
        select(HourlyForecast, ForecastRun, Observation)
        .join(ForecastRun, HourlyForecast.forecast_run_id == ForecastRun.id)
        .join(
            Observation,
            and_(
                Observation.location_id == ForecastRun.location_id,
                Observation.observed_at == HourlyForecast.valid_time,
            ),
        )
        .where(ForecastRun.location_id == location_id)
        .where(HourlyForecast.valid_time >= ForecastRun.retrieved_at)
        .order_by(ForecastRun.id, HourlyForecast.valid_time, Observation.id)
    )

    samples = (
        EvaluationSample(
            variable=field,
            retrieved_at=run.retrieved_at,
            valid_time=forecast.valid_time,
            forecast_value=getattr(forecast, field),
            observation_value=getattr(observation, field),
        )
        for forecast, run, observation in result.tuples()
        for field in COMPARABLE_FIELDS
    )
    return calculate_metrics(samples)
