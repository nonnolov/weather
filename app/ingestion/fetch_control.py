"""One acquisition per small geographic cell, with independent durable state.

Location IDs, recipient scopes and accepted alert baselines remain unchanged.
Only Open-Meteo can enter this durable cache. Google hourly retention differs.
"""
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from zoneinfo import ZoneInfo
from sqlalchemy import select, text
from app.core.config import settings
from app.models.forecast_fetch import ForecastFetchCache, ProviderRequestBudget
from app.providers.base import (
    ProviderForecastResult, NormalizedHourlyForecast, NormalizedDailyForecast,
)


class ForecastControlError(RuntimeError):
    pass


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def acquisition_scope(location, days, now):
    lat, lon = float(location.latitude), float(location.longitude)
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ForecastControlError("Invalid forecast coordinates")
    # 0.002-degree cells: at most ~157 m from the query point near the equator.
    # Boundaries deliberately stay separate. Never merge whole districts.
    if location.slug.startswith("gps-location-"):
        lat = round(lat / 0.002) * 0.002
        lon = round(lon / 0.002) * 0.002
    local_date = utc(now).astimezone(ZoneInfo(location.timezone)).date().isoformat()
    identity = ["cell-v1", location.provider, round(lat, 8), round(lon, 8),
                location.timezone, location.country_code, location.province,
                location.district, location.subdistrict, days, local_date]
    key = sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    return key, lat, lon


async def lock_key(db, namespace):
    if db.bind.dialect.name == "postgresql":
        key = int.from_bytes(sha256(namespace.encode()).digest()[:8], "big", signed=True)
        await db.execute(text("SET LOCAL lock_timeout = '5000ms'"))
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


async def reserve_requests(sessions, provider, count, *, now=None):
    """Reserve before HTTP in a separate committed transaction.

    Failed/uncertain requests are never refunded. A planned batch may reserve
    more than actually used; the counter is an upper bound, not an invoice.
    Both UTC and Los Angeles month/day buckets prevent early boundary resets.
    Other apps using the same Google billing account are outside this ledger.
    """
    now = utc(now or datetime.now(timezone.utc))
    if count < 1 or not isinstance(count, int):
        raise ForecastControlError("Invalid request count")
    periods = {"m:" + now.strftime("%Y-%m"), "d:" + now.strftime("%Y-%m-%d"),
               "m:" + now.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m"),
               "d:" + now.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")}
    async with sessions() as db:
        await lock_key(db, "provider-budget:" + provider)
        rows = []
        for period in sorted(periods):
            row = await db.get(ProviderRequestBudget, (provider, period))
            if row is None:
                row = ProviderRequestBudget(provider=provider, period=period, reserved=0)
                db.add(row)
            limit = 0
            if provider == "google_weather":
                limit = settings.GOOGLE_WEATHER_MONTHLY_LIMIT if period.startswith("m:") else settings.GOOGLE_WEATHER_DAILY_LIMIT
            if limit and row.reserved + count > limit:
                raise ForecastControlError("Provider request budget exhausted")
            rows.append(row)
        for row in rows:
            row.reserved += count
        await db.commit()


def encode_result(result):
    data = asdict(result)
    return json.loads(json.dumps(data, default=lambda v: v.isoformat()))


def decode_result(data):
    return ProviderForecastResult(
        provider=data["provider"], retrieved_at=datetime.fromisoformat(data["retrieved_at"]),
        model_run_time=datetime.fromisoformat(data["model_run_time"]) if data["model_run_time"] else None,
        hourly=[NormalizedHourlyForecast(**{**row, "valid_time": datetime.fromisoformat(row["valid_time"])}) for row in data["hourly"]],
        daily=[NormalizedDailyForecast(**{**row, "forecast_date": date.fromisoformat(row["forecast_date"]),
               "sunrise": datetime.fromisoformat(row["sunrise"]) if row["sunrise"] else None,
               "sunset": datetime.fromisoformat(row["sunset"]) if row["sunset"] else None}) for row in data["daily"]],
        metadata=data["metadata"],
    )


async def fetch_shared_forecast(location, days, provider, sessions, *, clock=lambda: datetime.now(timezone.utc)):
    if location.provider != "open_meteo":
        raise ForecastControlError("Provider is not approved for durable forecast storage")
    now = utc(clock())
    key, latitude, longitude = acquisition_scope(location, days, now)
    error = None
    async with sessions() as cache_db:
        await lock_key(cache_db, "forecast-acquisition:" + key)
        row = await cache_db.get(ForecastFetchCache, key)
        if row is not None and row.payload is not None:
            age = now - utc(row.fetched_at)
            if timedelta(0) <= age < timedelta(seconds=settings.FORECAST_REFRESH_SECONDS):
                result = decode_result(row.payload)
                result.metadata["acquisition_cache_hit"] = True
                return result
        if row is not None and row.retry_after is not None and now < utc(row.retry_after):
            raise ForecastControlError("Forecast retry cooling down")
        if row is None:
            row = ForecastFetchCache(key=key)
            cache_db.add(row)
        # A committed reservation survives any later caller rollback or crash.
        await reserve_requests(sessions, location.provider, 1, now=now)
        try:
            result = await provider.fetch_forecast(latitude=latitude, longitude=longitude,
                forecast_days=days, timezone=location.timezone)
            if result.provider != location.provider or not result.hourly:
                raise ForecastControlError("Incomplete provider forecast")
            fetched = utc(result.retrieved_at)
            if fetched > utc(clock()) + timedelta(minutes=5):
                raise ForecastControlError("Provider timestamp is in the future")
            result.metadata = {**result.metadata, "acquisition_key": key,
                "acquisition_policy": "cell-v1", "query_latitude": latitude,
                "query_longitude": longitude, "acquisition_cache_hit": False}
            row.payload = encode_result(result)
            row.fetched_at = fetched
            row.retry_after = None
        except Exception:
            # Sanitized error: upstream URLs may contain keys or coordinates.
            row.retry_after = utc(clock()) + timedelta(seconds=settings.FORECAST_FAILURE_BACKOFF_SECONDS)
            error = ForecastControlError("Provider forecast fetch failed")
        await cache_db.commit()
    if error:
        raise error
    return result
