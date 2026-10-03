import pytest
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.base import (
    BaseWeatherProvider,
    NormalizedHourlyForecast,
    NormalizedDailyForecast,
    ProviderForecastResult,
)
from app.providers.open_meteo import OpenMeteoProvider
from app.providers.registry import get_provider, list_providers


# ── Registry tests ────────────────────────────────────────────────────────────

def test_registry_lists_open_meteo() -> None:
    assert "open_meteo" in list_providers()


def test_registry_get_open_meteo() -> None:
    provider = get_provider("open_meteo")
    assert provider.name == "open_meteo"


def test_registry_unknown_provider_raises() -> None:
    with pytest.raises(KeyError, match="Unknown provider"):
        get_provider("nonexistent_provider")


# ── OpenMeteoProvider unit tests ──────────────────────────────────────────────

OPEN_METEO_SAMPLE_RESPONSE = {
    "latitude": 35.68,
    "longitude": 139.69,
    "elevation": 44.0,
    "generationtime_ms": 1.23,
    "utc_offset_seconds": 32400,
    "hourly": {
        "time": ["2024-06-01T00:00", "2024-06-01T01:00"],
        "temperature_2m": [20.5, 21.0],
        "apparent_temperature": [19.0, 19.5],
        "dewpoint_2m": [15.0, 15.5],
        "relative_humidity_2m": [70.0, 72.0],
        "precipitation": [0.0, 0.1],
        "precipitation_probability": [10.0, 20.0],
        "rain": [0.0, 0.1],
        "snowfall": [0.0, 0.0],
        "snow_depth": [0.0, 0.0],
        "weather_code": [0, 1],
        "cloud_cover": [10.0, 20.0],
        "surface_pressure": [1013.0, 1012.5],
        "wind_speed_10m": [5.0, 6.0],
        "wind_direction_10m": [180.0, 190.0],
        "wind_gusts_10m": [8.0, 9.0],
        "visibility": [10000.0, 9500.0],
        "uv_index": [0.0, 0.5],
        "is_day": [0, 0],
    },
    "daily": {
        "time": ["2024-06-01", "2024-06-02"],
        "temperature_2m_max": [26.0, 27.0],
        "temperature_2m_min": [18.0, 19.0],
        "apparent_temperature_max": [25.0, 26.0],
        "apparent_temperature_min": [17.0, 18.0],
        "precipitation_sum": [0.0, 1.0],
        "precipitation_probability_max": [10.0, 40.0],
        "rain_sum": [0.0, 1.0],
        "snowfall_sum": [0.0, 0.0],
        "weather_code": [0, 61],
        "wind_speed_10m_max": [10.0, 12.0],
        "wind_gusts_10m_max": [15.0, 18.0],
        "wind_direction_10m_dominant": [180.0, 200.0],
        "uv_index_max": [5.0, 6.0],
        "sunrise": ["2024-06-01T04:25", "2024-06-02T04:24"],
        "sunset": ["2024-06-01T18:55", "2024-06-02T18:56"],
    },
}


def _make_mock_response(data: dict) -> AsyncMock:
    """
    Build a mock httpx.Response where:
    - .raise_for_status() is a plain synchronous no-op (httpx Response.raise_for_status is sync)
    - .json() is a plain synchronous call returning the dict (httpx Response.json is sync)
    Using MagicMock for these two attributes prevents AsyncMock from wrapping
    them as coroutines, which would cause 'coroutine object has no attribute get'.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = data
    mock_response.raise_for_status.return_value = None
    return mock_response


@pytest.mark.asyncio
async def test_open_meteo_fetch_parses_hourly() -> None:
    provider = OpenMeteoProvider()
    mock_response = _make_mock_response(OPEN_METEO_SAMPLE_RESPONSE)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.fetch_forecast(35.68, 139.69, forecast_days=2)

    assert result.provider == "open_meteo"
    assert len(result.hourly) == 2
    assert result.hourly[0].temperature_2m == 20.5
    assert result.hourly[1].temperature_2m == 21.0
    assert result.hourly[0].is_day is False


@pytest.mark.asyncio
async def test_open_meteo_fetch_parses_daily() -> None:
    provider = OpenMeteoProvider()
    mock_response = _make_mock_response(OPEN_METEO_SAMPLE_RESPONSE)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.fetch_forecast(35.68, 139.69, forecast_days=2)

    assert len(result.daily) == 2
    assert result.daily[0].forecast_date == date(2024, 6, 1)
    assert result.daily[0].temperature_2m_max == 26.0
    assert result.daily[1].weather_code == 61


@pytest.mark.asyncio
async def test_open_meteo_fetch_parses_sunrise_sunset() -> None:
    provider = OpenMeteoProvider()
    mock_response = _make_mock_response(OPEN_METEO_SAMPLE_RESPONSE)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.fetch_forecast(35.68, 139.69, forecast_days=2)

    assert result.daily[0].sunrise is not None
    assert result.daily[0].sunset is not None


@pytest.mark.asyncio
async def test_open_meteo_metadata() -> None:
    provider = OpenMeteoProvider()
    mock_response = _make_mock_response(OPEN_METEO_SAMPLE_RESPONSE)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.fetch_forecast(35.68, 139.69)

    assert result.metadata["elevation"] == 44.0


@pytest.mark.asyncio
async def test_open_meteo_fetch_observations_uses_archive_endpoint() -> None:
    provider = OpenMeteoProvider()
    mock_response = _make_mock_response(OPEN_METEO_SAMPLE_RESPONSE)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as get:
        result = await provider.fetch_observations(
            35.68, 139.69, date(2024, 6, 1), date(2024, 6, 1), "Asia/Tokyo"
        )

    assert result.provider == "open_meteo"
    assert len(result.observations) == 2
    assert result.observations[0].temperature_2m == 20.5
    assert result.observations[0].valid_time == datetime(2024, 5, 31, 15, tzinfo=timezone.utc)
    assert get.call_args.args[0] == "https://archive-api.open-meteo.com/v1/archive"
    assert get.call_args.kwargs["params"]["start_date"] == "2024-06-01"
