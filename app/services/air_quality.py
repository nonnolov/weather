"""Separate model air-quality adapter. No weather ingestion or notifications."""
import asyncio
import copy
import json
import math
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import httpx

URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
CACHE_SECONDS = 600
MAX_CACHE = 128
MAX_BODY = 65536
SOURCE = {
    "provider": "Open-Meteo",
    "model": "CAMS Global Atmospheric Composition Forecast",
    "source_type": "model_estimate",
    "spatial_resolution_km": 45,
    "native_temporal_resolution_hours": 3,
    "output_temporal_resolution_hours": 1,
    "pm25_unit": "µg/m³",
    "aqi_standard": "European AQI (Open-Meteo)",
    "model_run_at": None,
    "source_url": "https://open-meteo.com/en/docs/air-quality-api",
    "cams_url": "https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts",
}
LEVELS = ((20, "good"), (40, "fair"), (60, "moderate"),
          (80, "poor"), (100, "very_poor"), (math.inf, "extremely_poor"))

class AirQualityError(Exception):
    """Sanitized provider failure; never expose URLs with coordinates."""

def number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None

def level(aqi):
    if aqi is None:
        return None
    return next(name for maximum, name in LEVELS if aqi <= maximum)

def normalize(payload, retrieved_at):
    if retrieved_at.tzinfo is None:
        raise AirQualityError("invalid_clock")
    try:
        assert payload["utc_offset_seconds"] == 0
        units = payload["hourly_units"]
        assert units["time"] == "unixtime"
        assert units["pm2_5"] in {"µg/m³", "μg/m³"}
        assert units["european_aqi"] == "EAQI"
        hourly = payload["hourly"]
        times, pm, aqi = hourly["time"], hourly["pm2_5"], hourly["european_aqi"]
        assert isinstance(times, list) and 1 <= len(times) <= 48
        assert isinstance(pm, list) and isinstance(aqi, list)
        assert len(times) == len(pm) == len(aqi)
        assert all(type(t) is int and 946684800 <= t < 4102444800 and t % 3600 == 0 for t in times)
        assert all(b-a == 3600 for a,b in zip(times,times[1:]))
    except (KeyError, TypeError, AssertionError):
        raise AirQualityError("invalid_payload") from None
    return {"retrieved_at": retrieved_at.astimezone(timezone.utc),
            "hourly": [{"valid_time": datetime.fromtimestamp(t, timezone.utc),
                        "pm25": number(p), "aqi": number(a)}
                       for t,p,a in zip(times,pm,aqi)]}

async def fetch_air_quality(latitude, longitude):
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise AirQualityError("invalid_coordinates")
    params = {"latitude": latitude, "longitude": longitude, "domains": "cams_global",
              "hourly": "pm2_5,european_aqi", "timezone": "GMT",
              "timeformat": "unixtime", "forecast_hours": 25, "past_hours": 1}
    try:
        async with asyncio.timeout(10):
            async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
                async with client.stream("GET", URL, params=params) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BODY:
                            raise AirQualityError("response_too_large")
        return normalize(json.loads(body), datetime.now(timezone.utc))
    except AirQualityError:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, UnicodeError):
        raise AirQualityError("provider_unavailable") from None

def render(data, now, error=None):
    report = {"status": "unavailable", "source": dict(SOURCE), "retrieved_at": None,
              "current": None, "hourly": [], "error_code": error,
              "measurement_available": False, "stale": False}
    if data is None:
        return report
    retrieved = data["retrieved_at"]
    report["retrieved_at"] = retrieved.isoformat()
    stale = bool(error) or now - retrieved > timedelta(hours=1) or retrieved > now + timedelta(minutes=5)
    candidates = [row for row in data["hourly"] if timedelta(0) <= now-row["valid_time"] < timedelta(hours=2)]
    current = candidates[-1] if candidates else None
    if current and now-current["valid_time"] >= timedelta(hours=1):
        stale = True
    def item(row):
        return {"valid_time": row["valid_time"].isoformat(), "pm25": row["pm25"],
                "aqi": row["aqi"], "category": level(row["aqi"])}
    report["current"] = item(current) if current else None
    report["hourly"] = [item(row) for row in data["hourly"] if now < row["valid_time"] <= now+timedelta(hours=24)]
    report["stale"] = stale
    usable = current is not None and (current["pm25"] is not None or current["aqi"] is not None)
    report["status"] = "stale" if stale else "available" if usable else "missing"
    return report

class AirQualityService:
    """Bounded per-process cache and one provider request at a time."""
    def __init__(self, fetcher=fetch_air_quality, clock=None):
        self.fetcher = fetcher
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.cache = OrderedDict()
        self.lock = asyncio.Lock()

    async def get(self, latitude, longitude):
        key = (latitude, longitude)
        try:
            async with asyncio.timeout(12):
                async with self.lock:
                    now = self.clock()
                    entry = self.cache.get(key)
                    if entry is None or now-entry["attempted_at"] >= timedelta(seconds=CACHE_SECONDS):
                        previous = entry["data"] if entry else None
                        try:
                            data = await self.fetcher(latitude, longitude)
                            entry = {"attempted_at": self.clock(), "data": data, "error": None}
                        except AirQualityError:
                            entry = {"attempted_at": self.clock(), "data": previous, "error": "provider_unavailable"}
                        self.cache[key] = entry
                        while len(self.cache) > MAX_CACHE:
                            self.cache.popitem(last=False)
                    self.cache.move_to_end(key)
                    return render(copy.deepcopy(entry["data"]), self.clock(), entry["error"])
        except TimeoutError:
            entry = self.cache.get(key)
            return render(copy.deepcopy(entry["data"]) if entry else None, self.clock(), "provider_unavailable")

service = AirQualityService()

def get_air_quality_service():
    return service
