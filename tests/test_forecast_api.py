import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from httpx import AsyncClient

from tests.conftest import FakeWeatherProvider

LOCATION_PAYLOAD = {
    "name": "Osaka",
    "slug": "osaka",
    "latitude": 34.6937,
    "longitude": 135.5023,
    "timezone": "Asia/Tokyo",
    "country_code": "JP",
    "provider": "open_meteo",
}


async def _create_location(client: AsyncClient) -> int:
    resp = await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_ingest_endpoint_returns_201(client: AsyncClient) -> None:
    location_id = await _create_location(client)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        resp = await client.post(f"/api/v1/ingest/{location_id}")

    assert resp.status_code == 201
    data = resp.json()
    assert data["location_id"] == location_id
    assert data["provider"] == "open_meteo"
    assert data["hourly_records"] == 24
    assert data["daily_records"] == 7


@pytest.mark.asyncio
async def test_ingest_unknown_location_returns_404(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/ingest/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_forecast(client: AsyncClient) -> None:
    location_id = await _create_location(client)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        await client.post(f"/api/v1/ingest/{location_id}")

    resp = await client.get(f"/api/v1/forecast/{location_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["location_id"] == location_id
    assert len(data["hourly"]) == 24
    assert len(data["daily"]) == 7


@pytest.mark.asyncio
async def test_get_forecast_no_runs_returns_404(client: AsyncClient) -> None:
    location_id = await _create_location(client)
    resp = await client.get(f"/api/v1/forecast/{location_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_forecast_unknown_location_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/forecast/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_forecast_runs(client: AsyncClient) -> None:
    location_id = await _create_location(client)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        await client.post(f"/api/v1/ingest/{location_id}")
        await client.post(f"/api/v1/ingest/{location_id}")

    resp = await client.get(f"/api/v1/forecast/{location_id}/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 2
    # Newest first
    assert runs[0]["id"] > runs[1]["id"]


@pytest.mark.asyncio
async def test_forecast_hourly_fields(client: AsyncClient) -> None:
    """Verify key fields are present in hourly forecast response."""
    location_id = await _create_location(client)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        await client.post(f"/api/v1/ingest/{location_id}")

    resp = await client.get(f"/api/v1/forecast/{location_id}")
    hourly = resp.json()["hourly"][0]
    assert "valid_time" in hourly
    assert "temperature_2m" in hourly
    assert "precipitation" in hourly
    assert "weather_code" in hourly


@pytest.mark.asyncio
async def test_forecast_daily_fields(client: AsyncClient) -> None:
    """Verify key fields are present in daily forecast response."""
    location_id = await _create_location(client)
    fake = FakeWeatherProvider()

    with patch("app.ingestion.service.get_provider", return_value=fake):
        await client.post(f"/api/v1/ingest/{location_id}")

    resp = await client.get(f"/api/v1/forecast/{location_id}")
    daily = resp.json()["daily"][0]
    assert "forecast_date" in daily
    assert "temperature_2m_max" in daily
    assert "temperature_2m_min" in daily
