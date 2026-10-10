from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.providers.open_meteo import OpenMeteoProvider

ARCHIVE = {
    "utc_offset_seconds": 25200,
    "hourly": {
        "time": ["2024-01-01T01:00"],
        "temperature_2m": [28],
        "precipitation": [0],
        "rain": [0],
    },
}


@pytest.mark.asyncio
async def test_archive_supported_request_and_absent_fields_are_not_zero_filled():
    response = httpx.Response(200, json=ARCHIVE,
                              request=httpx.Request("GET", "https://archive-api.open-meteo.com"))
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
        result = await OpenMeteoProvider().fetch_observations(
            13, 100, date(2024, 1, 1), date(2024, 1, 1), "Asia/Bangkok",
        )
    variables = set(get.call_args.kwargs["params"]["hourly"].split(","))
    assert {"precipitation", "temperature_2m", "rain"} <= variables
    assert not variables & {"precipitation_probability", "visibility", "uv_index"}
    row = result.observations[0]
    assert row.valid_time == datetime(2023, 12, 31, 18, tzinfo=timezone.utc)
    assert row.precipitation == 0
    assert row.precipitation_probability is row.visibility is row.uv_index is None


@pytest.mark.asyncio
async def test_live_forecast_retains_probability_and_other_forecast_variables():
    response = httpx.Response(200, json=ARCHIVE,
                              request=httpx.Request("GET", "https://api.open-meteo.com"))
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
        await OpenMeteoProvider().fetch_forecast(13, 100)
    variables = set(get.call_args.kwargs["params"]["hourly"].split(","))
    assert {"precipitation_probability", "visibility", "uv_index"} <= variables


@pytest.mark.asyncio
async def test_archive_failure_never_becomes_fabricated_observations():
    response = httpx.Response(400, json={"error": True},
                              request=httpx.Request("GET", "https://archive-api.open-meteo.com"))
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
        with pytest.raises(httpx.HTTPStatusError):
            await OpenMeteoProvider().fetch_observations(
                13, 100, date(2024, 1, 1), date(2024, 1, 1),
            )
