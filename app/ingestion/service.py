"""Forecast ingestion service — orchestrates provider fetch → DB persistence."""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.location import Location
from app.models.forecast import ForecastRun, HourlyForecast, DailyForecast
from app.providers.base import ProviderForecastResult, NormalizedHourlyForecast, NormalizedDailyForecast
from app.providers.registry import get_provider
from app.core.config import settings


class IngestionError(Exception):
    pass


async def ingest_forecast_for_location(
    db: AsyncSession,
    location: Location,
    forecast_days: int | None = None,
) -> ForecastRun:
    """
    Fetch a fresh forecast for *location* from its configured provider,
    persist it as an immutable ForecastRun snapshot, and return the run.
    """
    days = forecast_days or settings.FORECAST_DAYS

    try:
        provider = get_provider(location.provider)
    except KeyError as exc:
        raise IngestionError(str(exc)) from exc

    try:
        result: ProviderForecastResult = await provider.fetch_forecast(
            latitude=location.latitude,
            longitude=location.longitude,
            forecast_days=days,
            timezone=location.timezone,
        )
    except Exception as exc:
        raise IngestionError(f"Provider fetch failed: {exc}") from exc

    # Persist the forecast run
    run = ForecastRun(
        location_id=location.id,
        provider=result.provider,
        retrieved_at=result.retrieved_at,
        model_run_time=result.model_run_time,
        forecast_days=days,
        raw_provider_metadata=str(result.metadata) if result.metadata else None,
    )
    db.add(run)
    await db.flush()  # get run.id without committing

    # Persist hourly records
    for h in result.hourly:
        db.add(_hourly_to_orm(run.id, h))

    # Persist daily records
    for d in result.daily:
        db.add(_daily_to_orm(run.id, d))

    await db.flush()
    return run


def _hourly_to_orm(run_id: int, h: NormalizedHourlyForecast) -> HourlyForecast:
    return HourlyForecast(
        forecast_run_id=run_id,
        valid_time=h.valid_time,
        temperature_2m=h.temperature_2m,
        apparent_temperature=h.apparent_temperature,
        dewpoint_2m=h.dewpoint_2m,
        relative_humidity_2m=h.relative_humidity_2m,
        precipitation=h.precipitation,
        precipitation_probability=h.precipitation_probability,
        rain=h.rain,
        snowfall=h.snowfall,
        snow_depth=h.snow_depth,
        weather_code=h.weather_code,
        cloud_cover=h.cloud_cover,
        surface_pressure=h.surface_pressure,
        wind_speed_10m=h.wind_speed_10m,
        wind_direction_10m=h.wind_direction_10m,
        wind_gusts_10m=h.wind_gusts_10m,
        visibility=h.visibility,
        uv_index=h.uv_index,
        is_day=h.is_day,
    )


def _daily_to_orm(run_id: int, d: NormalizedDailyForecast) -> DailyForecast:
    return DailyForecast(
        forecast_run_id=run_id,
        forecast_date=d.forecast_date,
        temperature_2m_max=d.temperature_2m_max,
        temperature_2m_min=d.temperature_2m_min,
        apparent_temperature_max=d.apparent_temperature_max,
        apparent_temperature_min=d.apparent_temperature_min,
        precipitation_sum=d.precipitation_sum,
        precipitation_probability_max=d.precipitation_probability_max,
        rain_sum=d.rain_sum,
        snowfall_sum=d.snowfall_sum,
        weather_code=d.weather_code,
        wind_speed_10m_max=d.wind_speed_10m_max,
        wind_gusts_10m_max=d.wind_gusts_10m_max,
        wind_direction_10m_dominant=d.wind_direction_10m_dominant,
        uv_index_max=d.uv_index_max,
        sunrise=d.sunrise,
        sunset=d.sunset,
    )
