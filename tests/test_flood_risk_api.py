from datetime import datetime, timedelta, timezone

import pytest

from app.models.forecast import ForecastRun, HourlyForecast
from app.models.location import Location


@pytest.mark.asyncio
async def test_forecast_rainfall_endpoint_uses_latest_run_and_keeps_risk_unassessed(client, db_session):
    location = Location(
        name="Flood test",
        slug="flood-test",
        latitude=13.0,
        longitude=100.0,
        timezone="Asia/Bangkok",
    )
    db_session.add(location)
    await db_session.flush()

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    run = ForecastRun(
        location_id=location.id,
        provider="open_meteo",
        retrieved_at=now,
        forecast_days=1,
    )
    db_session.add(run)
    await db_session.flush()
    first_end = now + timedelta(hours=2)
    for index in range(24):
        db_session.add(HourlyForecast(
            forecast_run_id=run.id,
            valid_time=first_end + timedelta(hours=index),
            precipitation=1.5,
        ))
    await db_session.flush()

    response = await client.get(f"/api/v1/flood-risk/{location.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["forecast_run_id"] == run.id
    assert body["assessment_method"] == "local_rainfall_duration_flood_potential_v1"
    assert body["assessment_status"] == "not_assessed"
    assert body["assessment_reason_codes"] == [
        "location_profile_unavailable",
    ]
    assert body["data_status"] == "available"
    assert body["hours_expected"] == body["hours_with_precipitation"] == 24
    assert body["rolling_accumulations"][0]["max_accumulation_mm"] == 1.5
    assert body["rolling_accumulations"][1]["max_accumulation_mm"] == 4.5
    assert body["measurement_available"] is False
    assert body["flood_occurrence_confirmed"] is False

    location.country_code = "TH"
    location.province = "Bangkok"
    await db_session.flush()
    assessed = (await client.get(f"/api/v1/flood-risk/{location.id}")).json()
    assert assessed["risk_detected"] is False
    assert assessed["assessment_status"] == "rainfall_below_trigger"
    # A different location must not receive this location's forecast.
    other = Location(name="Other", slug="other-flood", latitude=13, longitude=100,
                     country_code="TH", province="Bangkok")
    db_session.add(other)
    await db_session.flush()
    assert (await client.get(f"/api/v1/flood-risk/{other.id}")).status_code == 404

    location.is_active = False
    await db_session.flush()
    assert (await client.get(f"/api/v1/flood-risk/{location.id}")).status_code == 404
    assert (await client.get("/api/v1/flood-risk/999999")).status_code == 404


@pytest.mark.asyncio
async def test_forecast_rainfall_endpoint_reports_missing_forecast(client, db_session):
    location = Location(
        name="No forecast",
        slug="no-forecast",
        latitude=13.0,
        longitude=100.0,
        timezone="Asia/Bangkok",
    )
    db_session.add(location)
    await db_session.flush()
    response = await client.get(f"/api/v1/flood-risk/{location.id}")
    assert response.status_code == 404
