import pytest

from app.core.config import settings
from app.services.maintenance_guard import effective_admin_api_key


ADMIN_KEY = "test-admin-key-0123456789abcdef0123456789abcdef"


def enable_production_admin(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", ADMIN_KEY)


@pytest.mark.asyncio
async def test_privileged_endpoints_require_admin_key_in_production(client, monkeypatch):
    enable_production_admin(monkeypatch)

    create = await client.post("/api/v1/locations", json={
        "name": "Blocked",
        "slug": "blocked",
        "latitude": 13.0,
        "longitude": 100.0,
        "timezone": "Asia/Bangkok",
        "country_code": "TH",
        "provider": "open_meteo",
    })
    ingest = await client.post("/api/v1/ingest/1")
    patch = await client.patch("/api/v1/locations/1", json={"name": "Blocked"})
    delete = await client.delete("/api/v1/locations/1")

    assert create.status_code == 401
    assert ingest.status_code == 401
    assert patch.status_code == 401
    assert delete.status_code == 401


@pytest.mark.asyncio
async def test_wrong_admin_key_is_rejected_in_production(client, monkeypatch):
    enable_production_admin(monkeypatch)

    response = await client.post(
        "/api/v1/ingest/999999",
        headers={"X-Admin-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_correct_admin_key_passes_guard_in_production(client, monkeypatch):
    enable_production_admin(monkeypatch)

    response = await client.post(
        "/api/v1/ingest/999999",
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_location_reads_still_work_in_production(client, monkeypatch):
    enable_production_admin(monkeypatch)
    response = await client.get("/api/v1/locations")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_derived_admin_key_works_when_explicit_key_is_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", None)
    monkeypatch.setattr(settings, "SECRET_KEY", "production-secret-for-test-only-0123456789")

    response = await client.post(
        "/api/v1/ingest/999999",
        headers={"X-Admin-API-Key": effective_admin_api_key()},
    )
    assert response.status_code == 404
