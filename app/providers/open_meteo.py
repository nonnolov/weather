"""Open-Meteo provider — free, no API key required."""
from datetime import datetime, timezone as dt_timezone, date, timedelta
from typing import Any
import httpx

from app.core.config import settings
from app.providers.base import (
    BaseWeatherProvider,
    NormalizedHourlyForecast,
    NormalizedDailyForecast,
    ProviderForecastResult,
    ProviderObservationResult,
)

# Variables requested from the Open-Meteo hourly endpoint
_HOURLY_VARS = [
    "temperature_2m",
    "apparent_temperature",
    "dewpoint_2m",
    "relative_humidity_2m",
    "precipitation",
    "precipitation_probability",
    "rain",
    "snowfall",
    "snow_depth",
    "weather_code",
    "cloud_cover",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "visibility",
    "uv_index",
    "is_day",
]

_DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "rain_sum",
    "snowfall_sum",
    "weather_code",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "uv_index_max",
    "sunrise",
    "sunset",
]


class OpenMeteoProvider(BaseWeatherProvider):
    """Fetches forecasts from the Open-Meteo free API."""

    @property
    def name(self) -> str:
        return "open_meteo"

    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
        timezone: str = "UTC",
    ) -> ProviderForecastResult:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(_HOURLY_VARS),
            "daily": ",".join(_DAILY_VARS),
            "forecast_days": forecast_days,
            # Let Open-Meteo resolve the IANA timezone for locations that still
            # use the model default UTC timezone.
            "timezone": "auto" if timezone == "UTC" else timezone,
            "timeformat": "iso8601",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{settings.OPEN_METEO_BASE_URL}/forecast",
                params=params,
            )
            response.raise_for_status()

        raw: dict[str, Any] = response.json()
        retrieved_at = datetime.now(dt_timezone.utc)

        hourly = self._parse_hourly(raw)
        daily = self._parse_daily(raw)

        return ProviderForecastResult(
            provider=self.name,
            retrieved_at=retrieved_at,
            model_run_time=None,  # Open-Meteo does not expose model run time
            hourly=hourly,
            daily=daily,
            metadata={
                "elevation": raw.get("elevation"),
                "generationtime_ms": raw.get("generationtime_ms"),
                "utc_offset_seconds": raw.get("utc_offset_seconds"),
                "timezone": raw.get("timezone"),
                "timezone_abbreviation": raw.get("timezone_abbreviation"),
            },
        )

    async def fetch_observations(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str = "UTC",
    ) -> ProviderObservationResult:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(_HOURLY_VARS),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": timezone,
            "timeformat": "iso8601",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://archive-api.open-meteo.com/v1/archive", params=params
            )
            response.raise_for_status()

        raw: dict[str, Any] = response.json()
        return ProviderObservationResult(
            provider=self.name,
            observations=self._parse_hourly(raw),
            metadata={
                "elevation": raw.get("elevation"),
                "generationtime_ms": raw.get("generationtime_ms"),
                "utc_offset_seconds": raw.get("utc_offset_seconds"),
            },
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_hourly(self, raw: dict[str, Any]) -> list[NormalizedHourlyForecast]:
        hourly_data = raw.get("hourly", {})
        times = hourly_data.get("time", [])
        utc_offset_seconds = raw.get("utc_offset_seconds", 0)
        records: list[NormalizedHourlyForecast] = []

        for i, time_str in enumerate(times):
            valid_time = self._parse_dt(time_str, utc_offset_seconds)
            records.append(
                NormalizedHourlyForecast(
                    valid_time=valid_time,
                    temperature_2m=self._get(hourly_data, "temperature_2m", i),
                    apparent_temperature=self._get(hourly_data, "apparent_temperature", i),
                    dewpoint_2m=self._get(hourly_data, "dewpoint_2m", i),
                    relative_humidity_2m=self._get(hourly_data, "relative_humidity_2m", i),
                    precipitation=self._get(hourly_data, "precipitation", i),
                    precipitation_probability=self._get(hourly_data, "precipitation_probability", i),
                    rain=self._get(hourly_data, "rain", i),
                    snowfall=self._get(hourly_data, "snowfall", i),
                    snow_depth=self._get(hourly_data, "snow_depth", i),
                    weather_code=self._get(hourly_data, "weather_code", i),
                    cloud_cover=self._get(hourly_data, "cloud_cover", i),
                    surface_pressure=self._get(hourly_data, "surface_pressure", i),
                    wind_speed_10m=self._get(hourly_data, "wind_speed_10m", i),
                    wind_direction_10m=self._get(hourly_data, "wind_direction_10m", i),
                    wind_gusts_10m=self._get(hourly_data, "wind_gusts_10m", i),
                    visibility=self._get(hourly_data, "visibility", i),
                    uv_index=self._get(hourly_data, "uv_index", i),
                    is_day=bool(self._get(hourly_data, "is_day", i)) if self._get(hourly_data, "is_day", i) is not None else None,
                )
            )
        return records

    def _parse_daily(self, raw: dict[str, Any]) -> list[NormalizedDailyForecast]:
        daily_data = raw.get("daily", {})
        dates = daily_data.get("time", [])
        utc_offset_seconds = raw.get("utc_offset_seconds", 0)
        records: list[NormalizedDailyForecast] = []

        for i, date_str in enumerate(dates):
            forecast_date = date.fromisoformat(date_str)
            sunrise_raw = self._get(daily_data, "sunrise", i)
            sunset_raw = self._get(daily_data, "sunset", i)
            records.append(
                NormalizedDailyForecast(
                    forecast_date=forecast_date,
                    temperature_2m_max=self._get(daily_data, "temperature_2m_max", i),
                    temperature_2m_min=self._get(daily_data, "temperature_2m_min", i),
                    apparent_temperature_max=self._get(daily_data, "apparent_temperature_max", i),
                    apparent_temperature_min=self._get(daily_data, "apparent_temperature_min", i),
                    precipitation_sum=self._get(daily_data, "precipitation_sum", i),
                    precipitation_probability_max=self._get(daily_data, "precipitation_probability_max", i),
                    rain_sum=self._get(daily_data, "rain_sum", i),
                    snowfall_sum=self._get(daily_data, "snowfall_sum", i),
                    weather_code=self._get(daily_data, "weather_code", i),
                    wind_speed_10m_max=self._get(daily_data, "wind_speed_10m_max", i),
                    wind_gusts_10m_max=self._get(daily_data, "wind_gusts_10m_max", i),
                    wind_direction_10m_dominant=self._get(daily_data, "wind_direction_10m_dominant", i),
                    uv_index_max=self._get(daily_data, "uv_index_max", i),
                    sunrise=self._parse_dt(sunrise_raw, utc_offset_seconds) if sunrise_raw else None,
                    sunset=self._parse_dt(sunset_raw, utc_offset_seconds) if sunset_raw else None,
                )
            )
        return records

    @staticmethod
    def _get(data: dict, key: str, index: int) -> Any:
        values = data.get(key)
        if values is None or index >= len(values):
            return None
        return values[index]

    @staticmethod
    def _parse_dt(value: str | None, utc_offset_seconds: int | float = 0) -> datetime:
        if value is None:
            raise ValueError("Cannot parse None as datetime")
        # Open-Meteo returns ISO 8601 strings; may or may not include offset
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone(timedelta(seconds=utc_offset_seconds)))
        return dt.astimezone(dt_timezone.utc)
