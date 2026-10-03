from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.v1 import users as users_api
from app.models.forecast import ForecastRun
from app.models.location import Location
from app.models.user import User


async def _user_with_location(db_session, *, external_id="user-1"):
    location = Location(
        name="User GPS", slug=f"user-gps-{external_id}", latitude=13.2759,
        longitude=100.9286, province="Chon Buri", district="Mueang Chon Buri",
        subdistrict="Saen Suk", timezone="Asia/Bangkok", provider="open_meteo",
    )
    user = User(external_id=external_id, current_location=location)
    db_session.add(user)
    await db_session.flush()
    return user, location


@pytest.mark.asyncio
async def test_user_forecast_missing_user(client: AsyncClient):
    response = await client.get("/api/v1/users/missing/forecast")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_forecast_missing_location(client: AsyncClient, db_session):
    db_session.add(User(external_id="no-location"))
    await db_session.flush()
    response = await client.get("/api/v1/users/no-location/forecast")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_forecast_returns_latest_run(client: AsyncClient, db_session):
    user, location = await _user_with_location(db_session)
    run = ForecastRun(
        location_id=location.id, provider="open_meteo",
        retrieved_at=datetime(2024, 6, 1, tzinfo=timezone.utc), forecast_days=7,
    )
    db_session.add(run)
    await db_session.flush()
    response = await client.get(f"/api/v1/users/{user.external_id}/forecast")
    assert response.status_code == 200
    assert response.json()["location_id"] == location.id
    assert response.json()["id"] == run.id


@pytest.mark.asyncio
async def test_user_forecast_refresh_uses_current_location(
    client: AsyncClient, db_session, monkeypatch
):
    user, location = await _user_with_location(db_session)
    run = ForecastRun(
        location_id=location.id, provider="open_meteo",
        retrieved_at=datetime(2024, 6, 1, tzinfo=timezone.utc), forecast_days=7,
    )
    db_session.add(run)
    await db_session.flush()

    async def fake_ingest(db, selected_location, forecast_days=None):
        assert selected_location.id == location.id
        assert selected_location.latitude == 13.2759
        assert selected_location.longitude == 100.9286
        return run

    monkeypatch.setattr(users_api, "ingest_forecast_for_location", fake_ingest)
    response = await client.post(
        f"/api/v1/users/{user.external_id}/forecast/refresh"
    )
    assert response.status_code == 201
    assert response.json()["location_id"] == location.id
