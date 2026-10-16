"""Forecast ingestion service — orchestrates provider fetch → DB persistence."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from app.models.forecast import CurrentConditions, ForecastRun, HourlyForecast, DailyForecast
from app.models.observation import Observation
from app.providers.base import (
    NormalizedCurrentConditions,
    NormalizedDailyForecast,
    NormalizedHourlyForecast,
    ProviderForecastResult,
    ProviderObservationResult,
)
from app.providers.registry import get_provider
from app.core.config import settings


class IngestionError(Exception):
    pass


_OBSERVATION_INSERT_BATCH_SIZE = 1000


async def ingest_observations_for_location(
    db: AsyncSession,
    location: Location,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Fetch historical observations and insert only new location/timestamp rows."""
    end = end_date or (datetime.now(ZoneInfo("Asia/Bangkok")).date() - timedelta(days=1))
    start = start_date or end
    if start > end:
        raise IngestionError("start_date must be on or before end_date")

    try:
        provider = get_provider(location.provider)
    except KeyError as exc:
        raise IngestionError(str(exc)) from exc
    try:
        result: ProviderObservationResult = await provider.fetch_observations(
            latitude=location.latitude,
            longitude=location.longitude,
            start_date=start,
            end_date=end,
            timezone=location.timezone,
        )
    except Exception as exc:
        raise IngestionError(f"Provider observation fetch failed: {exc}") from exc

    values_by_time: dict[datetime, dict[str, object]] = {}
    for record in result.observations:
        values = _observation_values(location.id, result.provider, record)
        values_by_time[values["observed_at"]] = values
    if not values_by_time:
        return 0

    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect not in {"postgresql", "sqlite"}:
        raise IngestionError(f"Observation ingestion requires PostgreSQL or SQLite, got {dialect!r}")

    created = 0
    values = list(values_by_time.values())
    for offset in range(0, len(values), _OBSERVATION_INSERT_BATCH_SIZE):
        batch = values[offset:offset + _OBSERVATION_INSERT_BATCH_SIZE]
        if dialect == "postgresql":
            statement = postgresql_insert(Observation).values(batch)
        else:
            statement = sqlite_insert(Observation).values(batch)
        statement = statement.on_conflict_do_nothing(
            index_elements=("location_id", "observed_at")
        ).returning(Observation.id)
        result = await db.execute(statement)
        created += len(result.scalars().all())
    return created


async def ingest_seed_observations(
    db: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, int]:
    """Ingest observations for existing active Phase 3 seed locations only."""
    from app.seeds.locations import CHON_BURI_LOCATIONS

    slugs = [seed.slug for seed in CHON_BURI_LOCATIONS]
    result = await db.execute(
        select(Location).where(Location.slug.in_(slugs), Location.is_active.is_(True))
    )
    locations = {location.slug: location for location in result.scalars()}
    missing = [slug for slug in slugs if slug not in locations]
    if missing:
        raise IngestionError(f"Seed locations missing: {', '.join(missing)}")
    return {
        slug: await ingest_observations_for_location(db, locations[slug], start_date, end_date)
        for slug in slugs
    }


async def ingest_user_observations(
    db: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, int]:
    """Collect each active current user location once, retrying a rolling week.

    Keep seed ingestion available separately. Provider failures occur before
    inserts and are counted so one unavailable area does not block alerts.
    """
    from app.models.user import User

    end = end_date or (datetime.now(ZoneInfo("Asia/Bangkok")).date() - timedelta(days=1))
    start = start_date or (end - timedelta(days=6))
    if start > end:
        raise IngestionError("start_date must be on or before end_date")
    location_ids = select(User.current_location_id).where(User.current_location_id.is_not(None))
    locations = list((await db.scalars(
        select(Location).where(
            Location.id.in_(location_ids), Location.is_active.is_(True)
        ).order_by(Location.id)
    )).all())
    counts = {"locations": len(locations), "created": 0, "failed": 0}
    for location in locations:
        try:
            created = await ingest_observations_for_location(db, location, start, end)
            counts["created"] += created
        except IngestionError:
            counts["failed"] += 1
    return counts


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
    if location.provider == "google_weather":
        raise IngestionError("Google Weather is transient-only: usage rights and durable alert evidence are unresolved")

    try:
        provider = get_provider(location.provider)
    except KeyError as exc:
        raise IngestionError(str(exc)) from exc

    try:
        if settings.FORECAST_SHARING_ENABLED:
            from app.ingestion.fetch_control import fetch_shared_forecast
            from app.core.database import AsyncSessionLocal
            result = await fetch_shared_forecast(location, days, provider, AsyncSessionLocal)
        else:
            result = await provider.fetch_forecast(
                latitude=location.latitude, longitude=location.longitude,
                forecast_days=days, timezone=location.timezone,
            )
    except Exception as exc:
        raise IngestionError("Provider fetch failed") from exc

    if result.metadata.get("acquisition_cache_hit"):
        existing = await db.scalar(select(ForecastRun).where(
            ForecastRun.location_id == location.id,
            ForecastRun.provider == result.provider,
            ForecastRun.forecast_days == days,
            ForecastRun.retrieved_at == result.retrieved_at,
        ).order_by(ForecastRun.id.desc()).limit(1))
        if existing is not None:
            return existing

    # Open-Meteo returns the resolved IANA timezone when timezone=auto was used.
    resolved_timezone = result.metadata.get("timezone") if result.metadata else None
    if isinstance(resolved_timezone, str) and resolved_timezone:
        location.timezone = resolved_timezone

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

    if result.current is not None:
        db.add(_current_to_orm(run.id, result.current))

    # Persist hourly records
    for h in result.hourly:
        db.add(_hourly_to_orm(run.id, h))

    # Persist daily records
    for d in result.daily:
        db.add(_daily_to_orm(run.id, d))

    await db.flush()
    return run


def _current_to_orm(run_id: int, current: NormalizedCurrentConditions) -> CurrentConditions:
    return CurrentConditions(
        forecast_run_id=run_id,
        valid_time=current.valid_time,
        interval_seconds=current.interval_seconds,
        temperature_2m=current.temperature_2m,
        apparent_temperature=current.apparent_temperature,
        relative_humidity_2m=current.relative_humidity_2m,
        precipitation=current.precipitation,
        rain=current.rain,
        weather_code=current.weather_code,
        cloud_cover=current.cloud_cover,
        surface_pressure=current.surface_pressure,
        wind_speed_10m=current.wind_speed_10m,
        wind_direction_10m=current.wind_direction_10m,
        wind_gusts_10m=current.wind_gusts_10m,
        is_day=current.is_day,
    )


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


def _observation_values(
    location_id: int,
    provider: str,
    record: NormalizedHourlyForecast,
) -> dict[str, object]:
    if record.valid_time.tzinfo is None:
        raise IngestionError("Provider returned observation timestamp without timezone")
    return {
        "location_id": location_id,
        "observed_at": record.valid_time.astimezone(timezone.utc),
        "source": f"{provider}_historical",
        "temperature_2m": record.temperature_2m,
        "apparent_temperature": record.apparent_temperature,
        "dewpoint_2m": record.dewpoint_2m,
        "relative_humidity_2m": record.relative_humidity_2m,
        "precipitation": record.precipitation,
        "rain": record.rain,
        "snowfall": record.snowfall,
        "weather_code": record.weather_code,
        "cloud_cover": record.cloud_cover,
        "surface_pressure": record.surface_pressure,
        "wind_speed_10m": record.wind_speed_10m,
        "wind_direction_10m": record.wind_direction_10m,
        "wind_gusts_10m": record.wind_gusts_10m,
        "visibility": record.visibility,
        "uv_index": record.uv_index,
        "is_day": record.is_day,
    }
