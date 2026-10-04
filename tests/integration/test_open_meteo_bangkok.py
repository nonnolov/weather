"""Integration test against the real Open-Meteo forecast API."""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.providers.open_meteo import OpenMeteoProvider


BANGKOK_LATITUDE = 13.7563
BANGKOK_LONGITUDE = 100.5018
HTTP_TIMEOUT_SECONDS = 30.0


async def _fetch_open_meteo(
    client: httpx.AsyncClient,
    *,
    hourly: str,
) -> httpx.Response:
    try:
        return await client.get(
            f"{settings.OPEN_METEO_BASE_URL}/forecast",
            params={
                "latitude": BANGKOK_LATITUDE,
                "longitude": BANGKOK_LONGITUDE,
                "hourly": hourly,
                "forecast_days": 1,
                "timezone": "Asia/Bangkok",
            },
        )
    except httpx.RequestError as exc:
        pytest.skip(f"Open-Meteo network unavailable: {exc}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_open_meteo_bangkok_coordinates_match_request() -> None:
    """
    Call the real Open-Meteo API for Bangkok and verify that the response
    coordinates identify the same weather grid cell as the requested point.

    Network/API availability failures are skipped; invalid API responses or
    coordinate mismatches remain test failures.
    """
    provider = OpenMeteoProvider()

    try:
        result = await provider.fetch_forecast(
            latitude=BANGKOK_LATITUDE,
            longitude=BANGKOK_LONGITUDE,
            forecast_days=1,
            timezone="Asia/Bangkok",
        )
    except httpx.RequestError as exc:
        pytest.skip(f"Open-Meteo network unavailable: {exc}")

    assert result.provider == "open_meteo"
    assert result.hourly
    assert result.daily

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = await _fetch_open_meteo(client, hourly="temperature_2m")

    if response.status_code >= 500:
        pytest.skip(
            f"Open-Meteo API unavailable: HTTP {response.status_code}"
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        pytest.fail(f"Open-Meteo API returned an unexpected HTTP error: {exc}")

    raw = response.json()
    response_latitude = float(raw["latitude"])
    response_longitude = float(raw["longitude"])

    # Open-Meteo returns the selected forecast grid-cell coordinates.
    assert abs(response_latitude - BANGKOK_LATITUDE) <= 0.1
    assert abs(response_longitude - BANGKOK_LONGITUDE) <= 0.1

    print(
        f"Open-Meteo request=({BANGKOK_LATITUDE}, {BANGKOK_LONGITUDE}) "
        f"response=({response_latitude}, {response_longitude})"
    )
