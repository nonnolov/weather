from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.ingestion.service import IngestionError
from app.models.forecast import ForecastRun
from app.models.location import Location
from app.models.user import User


async def _create_user_location(db_session, external_id: str = "line-user-1") -> Location:
    location = Location(
        name="Stored location",
        slug=f"stored-location-{external_id}",
        latitude=13.7563,
        longitude=100.5018,
        timezone="Asia/Bangkok",
        provider="open_meteo",
    )
    db_session.add(User(external_id=external_id, current_location=location))
    await db_session.flush()
    return location


@pytest.mark.asyncio
async def test_get_user_forecast_returns_latest_stored_run(client: AsyncClient, db_session) -> None:
    location = await _create_user_location(db_session)
    earlier = ForecastRun(
        location_id=location.id,
        provider="open_meteo",
        retrieved_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        forecast_days=7,
    )
    latest = ForecastRun(
        location_id=location.id,
        provider="open_meteo",
        retrieved_at=datetime(2024, 6, 1, 1, tzinfo=timezone.utc),
        forecast_days=7,
    )
    db_session.add_all((earlier, latest))
    await db_session.flush()

    response = await client.get("/api/v1/users/line-user-1/forecast")

    assert response.status_code == 200
    assert response.json()["id"] == latest.id
    assert response.json()["location_id"] == location.id
    assert response.json()["current"] is None


@pytest.mark.asyncio
async def test_user_forecast_returns_404_for_missing_user_location_or_run(
    client: AsyncClient, db_session
) -> None:
    assert (await client.get("/api/v1/users/missing/forecast")).status_code == 404

    db_session.add(User(external_id="no-location"))
    await db_session.flush()
    assert (await client.get("/api/v1/users/no-location/forecast")).status_code == 404

    await _create_user_location(db_session, "no-forecast")
    assert (await client.get("/api/v1/users/no-forecast/forecast")).status_code == 404


@pytest.mark.asyncio
async def test_refresh_user_forecast_uses_stored_location_and_maps_failure(
    client: AsyncClient, db_session
) -> None:
    location = await _create_user_location(db_session)
    run = ForecastRun(
        location_id=location.id,
        provider="open_meteo",
        retrieved_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        forecast_days=4,
    )
    db_session.add(run)
    await db_session.flush()

    ingest = AsyncMock(return_value=run)
    with patch("app.api.v1.users.ingest_forecast_for_location", ingest):
        response = await client.post("/api/v1/users/line-user-1/forecast/refresh?forecast_days=4")

    assert response.status_code == 201
    assert response.json()["forecast_run_id"] == run.id
    assert ingest.await_args.args[1].id == location.id
    assert ingest.await_args.args[1].latitude == 13.7563
    assert ingest.await_args.args[1].longitude == 100.5018
    assert ingest.await_args.kwargs["forecast_days"] == 4

    with patch(
        "app.api.v1.users.ingest_forecast_for_location",
        AsyncMock(side_effect=IngestionError("Provider fetch failed: unavailable")),
    ):
        failure = await client.post("/api/v1/users/line-user-1/forecast/refresh")

    assert failure.status_code == 502
