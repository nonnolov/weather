"""Abstract base class for all weather providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any


@dataclass
class NormalizedHourlyForecast:
    """Provider-agnostic hourly forecast record."""
    valid_time: datetime
    temperature_2m: float | None = None          # °C
    apparent_temperature: float | None = None    # °C
    dewpoint_2m: float | None = None             # °C
    relative_humidity_2m: float | None = None   # %
    precipitation: float | None = None           # mm
    precipitation_probability: float | None = None  # %
    rain: float | None = None                    # mm
    snowfall: float | None = None                # cm
    snow_depth: float | None = None              # m
    weather_code: int | None = None              # WMO code
    cloud_cover: float | None = None             # %
    surface_pressure: float | None = None        # hPa
    wind_speed_10m: float | None = None          # km/h
    wind_direction_10m: float | None = None      # °
    wind_gusts_10m: float | None = None          # km/h
    visibility: float | None = None              # m
    uv_index: float | None = None
    is_day: bool | None = None


@dataclass
class NormalizedDailyForecast:
    """Provider-agnostic daily forecast record."""
    forecast_date: date
    temperature_2m_max: float | None = None
    temperature_2m_min: float | None = None
    apparent_temperature_max: float | None = None
    apparent_temperature_min: float | None = None
    precipitation_sum: float | None = None       # mm
    precipitation_probability_max: float | None = None  # %
    rain_sum: float | None = None                # mm
    snowfall_sum: float | None = None            # cm
    weather_code: int | None = None
    wind_speed_10m_max: float | None = None      # km/h
    wind_gusts_10m_max: float | None = None      # km/h
    wind_direction_10m_dominant: float | None = None  # °
    uv_index_max: float | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None


@dataclass
class ProviderForecastResult:
    """Complete normalised result returned by a provider fetch."""
    provider: str
    retrieved_at: datetime
    model_run_time: datetime | None
    hourly: list[NormalizedHourlyForecast] = field(default_factory=list)
    daily: list[NormalizedDailyForecast] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseWeatherProvider(ABC):
    """
    All provider implementations must subclass this.
    Provider-specific HTTP calls and data mapping stay entirely inside
    the subclass — nothing leaks into the ingestion layer.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier, e.g. 'open_meteo'."""
        ...

    @abstractmethod
    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
        timezone: str = "UTC",
    ) -> ProviderForecastResult:
        """
        Fetch and normalise a forecast for the given coordinates.
        Must never return fabricated data — always call the real API.
        """
        ...
