import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_privileged_endpoints_are_disabled_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")

    create = await client.post("/api/v1/locations", json={
        "name": "Blocked",
        "slug": "blocked",
        "latitude": 13.0,
        "longitude": 100.0,
        "timezone": "Asia/Bangkok",
        "country_code": "TH",
        "provider": "open_meteo",
    })
    gps = await client.post(
        "/api/v1/locations/from-gps",
        json={"latitude": 13.0, "longitude": 100.0},
    )
    ingest = await client.post("/api/v1/ingest/1")
    patch = await client.patch("/api/v1/locations/1", json={"name": "Blocked"})
    delete = await client.delete("/api/v1/locations/1")

    assert create.status_code == 403
    assert gps.status_code == 403
    assert ingest.status_code == 403
    assert patch.status_code == 403
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_public_location_reads_still_work_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    response = await client.get("/api/v1/locations")
    assert response.status_code == 200
