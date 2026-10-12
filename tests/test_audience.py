from uuid import uuid4
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import select
from app.main import app
from app.core.config import settings
from app.models import User
from app.models.audience import AudienceMember
from app.services.line_identity import LineIdentity, require_line_identity

@pytest.mark.asyncio
async def test_read_does_not_count_and_returns_only_totals(client):
    response = await client.get("/api/v1/audience")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"line_accounts": 0, "website_visitors": 0}

@pytest.mark.asyncio
async def test_reload_is_idempotent_and_distinct_browsers_count(client, db_session):
    visitor = str(uuid4())
    for _ in range(3):
        response = await client.post("/api/v1/audience/visit", json={"visitor_id": visitor})
        assert response.status_code == 200
        assert response.json() == {"line_accounts": 0, "website_visitors": 1}
    response = await client.post("/api/v1/audience/visit", json={"visitor_id": str(uuid4())})
    assert response.json() == {"line_accounts": 0, "website_visitors": 2}
    rows = (await db_session.scalars(select(AudienceMember))).all()
    assert len(rows) == 2
    assert all(visitor not in row.identity_hash and len(row.identity_hash) == 64 for row in rows)

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"visitor_id": "not-a-uuid"},
    {"visitor_id": str(uuid4()), "kind": "line"},
    {"visitor_id": str(uuid4()), "line_accounts": 500},
])
async def test_browser_cannot_supply_line_count_or_invalid_identity(client, payload):
    assert (await client.post("/api/v1/audience/visit", json=payload)).status_code == 422
    assert (await client.get("/api/v1/audience")).json() == {"line_accounts": 0, "website_visitors": 0}

@pytest.fixture
def line_enabled(monkeypatch):
    for key, value in {
        "LINE_SUBSCRIPTIONS_ENABLED": True, "LINE_LOGIN_CHANNEL_ID": "123",
        "LINE_CHANNEL_SECRET": "mock-secret", "LINE_CHANNEL_ACCESS_TOKEN": "mock-token",
        "LINE_OFFICIAL_ACCOUNT_ID": "@weather",
    }.items():
        monkeypatch.setattr(settings, key, value)

@pytest.mark.asyncio
async def test_unverified_user_and_rejected_login_do_not_count(client, db_session, line_enabled):
    db_session.add(User(external_id="U" + "a"*32))
    await db_session.flush()
    assert (await client.get("/api/v1/line/onboarding")).status_code == 401
    assert (await client.get("/api/v1/audience")).json()["line_accounts"] == 0

@pytest.mark.asyncio
async def test_verified_account_deduplicates_across_logins_without_subscribing(client, line_enabled):
    uid = "U" + "b"*32
    app.dependency_overrides[require_line_identity] = lambda: LineIdentity(uid, "mock-token")
    try:
        with patch("app.api.v1.line_onboarding.line_friendship", AsyncMock(return_value=False)):
            for _ in range(3):
                response = await client.get("/api/v1/line/onboarding")
                assert response.status_code == 200
                assert response.json()["enabled"] is False
            assert (await client.get("/api/v1/audience")).json()["line_accounts"] == 1
            app.dependency_overrides[require_line_identity] = lambda: LineIdentity("U" + "c"*32, "mock-token")
            assert (await client.get("/api/v1/line/onboarding")).status_code == 200
            assert (await client.get("/api/v1/audience")).json()["line_accounts"] == 2
    finally:
        app.dependency_overrides.pop(require_line_identity, None)
