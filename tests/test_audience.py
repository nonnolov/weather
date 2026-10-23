from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from app.main import app
from app.core.config import settings
from app.models import Location
from app.models.audience import AudienceMember
from app.services.geocoding import get_reverse_geocoder, ReverseGeocodingError
from app.services.line_identity import LineIdentity, require_line_identity

@pytest.mark.asyncio
async def test_read_does_not_count_and_returns_only_totals(client):
    response = await client.get("/api/v1/audience")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"received_locations": 0, "website_visitors": 0}

@pytest.mark.asyncio
async def test_reload_is_idempotent_and_distinct_browsers_count(client, db_session):
    visitor = str(uuid4())
    for _ in range(3):
        response = await client.post("/api/v1/audience/visit", json={"visitor_id": visitor})
        assert response.status_code == 200
        assert response.json() == {"received_locations": 0, "website_visitors": 1}
    response = await client.post("/api/v1/audience/visit", json={"visitor_id": str(uuid4())})
    assert response.json() == {"received_locations": 0, "website_visitors": 2}
    rows = (await db_session.scalars(select(AudienceMember))).all()
    assert len(rows) == 2
    assert all(visitor not in row.identity_hash and len(row.identity_hash) == 64 for row in rows)

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"visitor_id": "not-a-uuid"},
    {"visitor_id": str(uuid4()), "kind": "location"},
    {"visitor_id": str(uuid4()), "received_locations": 500},
])
async def test_client_cannot_supply_location_count_or_invalid_identity(client, payload):
    assert (await client.post("/api/v1/audience/visit", json=payload)).status_code == 422
    assert (await client.get("/api/v1/audience")).json() == {"received_locations": 0, "website_visitors": 0}

@pytest.fixture
def geocoder():
    geo = SimpleNamespace(reverse=AsyncMock(return_value=SimpleNamespace(
        province="Bangkok", district="Test", subdistrict="Test", country_code="TH")))
    app.dependency_overrides[get_reverse_geocoder] = lambda: geo
    yield geo
    app.dependency_overrides.pop(get_reverse_geocoder, None)

@pytest.mark.asyncio
async def test_seed_location_does_not_count(client, db_session):
    db_session.add(Location(name="Sample", slug="sample", latitude=1, longitude=2))
    await db_session.flush()
    assert (await client.get("/api/v1/audience")).json()["received_locations"] == 0

@pytest.mark.asyncio
async def test_saved_gps_deduplicates_across_users_and_retains_previous_area(client, geocoder):
    gps={"latitude":13.75, "longitude":100.5}
    for user in ["browser-one", "browser-one", "browser-two"]:
        assert (await client.post("/api/v1/users/"+user+"/location/from-gps",json=gps)).status_code == 200
    assert (await client.get("/api/v1/audience")).json()["received_locations"] == 1
    assert (await client.post("/api/v1/users/browser-one/location/from-gps",
        json={"latitude":13.8,"longitude":100.5})).status_code == 200
    assert (await client.get("/api/v1/audience")).json()["received_locations"] == 2

@pytest.mark.asyncio
async def test_failed_location_resolution_does_not_count(client, geocoder):
    geocoder.reverse.side_effect=ReverseGeocodingError("Unavailable")
    response=await client.post("/api/v1/users/browser-one/location/from-gps",
        json={"latitude":13.75,"longitude":100.5})
    assert response.status_code == 502
    assert (await client.get("/api/v1/audience")).json()["received_locations"] == 0

@pytest.mark.asyncio
async def test_line_gps_and_browser_gps_share_the_same_location_counter(client, geocoder, monkeypatch):
    for key,value in {"LINE_SUBSCRIPTIONS_ENABLED":True,"LINE_LOGIN_CHANNEL_ID":"123",
        "LINE_CHANNEL_SECRET":"mock-secret","LINE_CHANNEL_ACCESS_TOKEN":"mock-token",
        "LINE_OFFICIAL_ACCOUNT_ID":"@weather"}.items():
        monkeypatch.setattr(settings,key,value)
    app.dependency_overrides[require_line_identity]=lambda:LineIdentity("U"+"a"*32,"mock-token")
    try:
        gps={"latitude":13.75,"longitude":100.5}
        assert (await client.post("/api/v1/line/location/from-gps",json=gps)).status_code == 200
        assert (await client.post("/api/v1/users/browser-two/location/from-gps",json=gps)).status_code == 200
        assert (await client.get("/api/v1/audience")).json()["received_locations"] == 1
    finally:
        app.dependency_overrides.pop(require_line_identity,None)
