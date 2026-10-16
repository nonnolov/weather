from datetime import datetime, date
from pydantic import BaseModel, Field


class CurrentConditionsRead(BaseModel):
    id: int
    forecast_run_id: int
    valid_time: datetime
    interval_seconds: int | None
    temperature_2m: float | None
    apparent_temperature: float | None
    relative_humidity_2m: float | None
    precipitation: float | None
    rain: float | None
    weather_code: int | None
    cloud_cover: float | None
    surface_pressure: float | None
    wind_speed_10m: float | None
    wind_direction_10m: float | None
    wind_gusts_10m: float | None
    is_day: bool | None

    model_config = {"from_attributes": True}


# ── Hourly ────────────────────────────────────────────────────────────────────

class HourlyForecastRead(BaseModel):
    id: int
    forecast_run_id: int
    valid_time: datetime
    temperature_2m: float | None
    apparent_temperature: float | None
    dewpoint_2m: float | None
    relative_humidity_2m: float | None
    precipitation: float | None
    precipitation_probability: float | None
    rain: float | None
    snowfall: float | None
    snow_depth: float | None
    weather_code: int | None
    cloud_cover: float | None
    surface_pressure: float | None
    wind_speed_10m: float | None
    wind_direction_10m: float | None
    wind_gusts_10m: float | None
    visibility: float | None
    uv_index: float | None
    is_day: bool | None

    model_config = {"from_attributes": True}


# ── Daily ─────────────────────────────────────────────────────────────────────

class DailyForecastRead(BaseModel):
    id: int
    forecast_run_id: int
    forecast_date: date
    temperature_2m_max: float | None
    temperature_2m_min: float | None
    apparent_temperature_max: float | None
    apparent_temperature_min: float | None
    precipitation_sum: float | None
    precipitation_probability_max: float | None
    rain_sum: float | None
    snowfall_sum: float | None
    weather_code: int | None
    wind_speed_10m_max: float | None
    wind_gusts_10m_max: float | None
    wind_direction_10m_dominant: float | None
    uv_index_max: float | None
    sunrise: datetime | None
    sunset: datetime | None

    model_config = {"from_attributes": True}


# ── Forecast Run ──────────────────────────────────────────────────────────────

class ForecastRunRead(BaseModel):
    id: int
    location_id: int
    provider: str
    retrieved_at: datetime
    model_run_time: datetime | None
    forecast_days: int

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class ForecastRunDetail(ForecastRunRead):
    current: CurrentConditionsRead | None = None
    hourly: list[HourlyForecastRead] = Field(default_factory=list)
    daily: list[DailyForecastRead] = Field(default_factory=list)


# ── Ingestion response ────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    forecast_run_id: int
    location_id: int
    provider: str
    hourly_records: int
    daily_records: int
    retrieved_at: datetime
    timezone: str
