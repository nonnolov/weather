from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import hashlib, hmac, base64, json
import httpx
import pytest
from app.main import app
from app.core.config import settings
from app.models import User, Location
from app.models.line_subscription import LineSubscription
from app.services.line_identity import LineIdentity, require_line_identity, verify_line_token
from app.services.geocoding import get_reverse_geocoder
from app.notifications.subscriptions import CONSENT_VERSION, recipient_eligible, recipient_condition
from sqlalchemy import select
UID = "U" + "a"*32

@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "LINE_SUBSCRIPTIONS_ENABLED", True)
    monkeypatch.setattr(settings, "LINE_LOGIN_CHANNEL_ID", "123")
    monkeypatch.setattr(settings, "LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setattr(settings, "LINE_CHANNEL_ACCESS_TOKEN", "mock-channel-token")
    monkeypatch.setattr(settings, "LINE_OFFICIAL_ACCOUNT_ID", "@weather")

@pytest.fixture
def identity(enabled):
    app.dependency_overrides[require_line_identity] = lambda: LineIdentity(UID, "mock-token")
    yield
    app.dependency_overrides.pop(require_line_identity, None)

async def area(db):
    location=Location(name="Test Bangkok", slug="onboarding-test", latitude=13.7563, longitude=100.5018, timezone="Asia/Bangkok", is_active=True)
    db.add(location);await db.flush()
    user=User(external_id=UID,current_location_id=location.id)
    db.add(user);await db.flush()
    return user,location

async def record(db, user, location, **kwargs):
    sub=LineSubscription(user_id=user.external_id, verified_location_id=location.id, friend=True, enabled=False, updated_at=datetime.now(timezone.utc), friend_event_time=0, **kwargs)
    db.add(sub);await db.flush();return sub

@pytest.mark.asyncio
async def test_config_and_feature_off(client,monkeypatch):
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",False)
    monkeypatch.setattr(settings,"LINE_OFFICIAL_ACCOUNT_ID","@weather")
    response=await client.get("/api/v1/line/onboarding/config")
    assert response.json()=={"enabled":False,"add_friend_url":"https://line.me/R/ti/p/%40weather"}
    assert (await client.get("/api/v1/line/onboarding")).status_code==503

@pytest.mark.asyncio
async def test_missing_token_rejected(client,enabled):
    assert (await client.get("/api/v1/line/onboarding")).status_code==401

@pytest.mark.asyncio
async def test_new_status_does_not_subscribe(client,identity,db_session):
    with patch("app.api.v1.line_onboarding.line_friendship",AsyncMock(return_value=False)):
        response=await client.get("/api/v1/line/onboarding")
    assert response.status_code==200
    assert response.json()["next_step"]=="friend"
    assert not response.json()["enabled"]
    assert await db_session.get(LineSubscription,UID) is None

@pytest.mark.asyncio
@pytest.mark.parametrize("reason",["not_friend","missing_area","wrong_consent","inactive_area"])
async def test_enable_requires_every_condition(client,identity,db_session,reason):
    user,location=await area(db_session)
    if reason!="missing_area":
        await record(db_session,user,location)
    if reason=="inactive_area":
        location.is_active=False;await db_session.flush()
    with patch("app.api.v1.line_onboarding.line_friendship",AsyncMock(return_value=reason!="not_friend")):
        response=await client.put("/api/v1/line/subscription",json={"enabled":True,"consent_version":"wrong" if reason=="wrong_consent" else CONSENT_VERSION})
    assert response.status_code==(422 if reason=="wrong_consent" else 409)
    sub=await db_session.get(LineSubscription,UID)
    assert not sub.enabled

@pytest.mark.asyncio
async def test_enable_and_disable(client,identity,db_session):
    user,location=await area(db_session);sub=await record(db_session,user,location)
    with patch("app.api.v1.line_onboarding.line_friendship",AsyncMock(return_value=True)):
        response=await client.put("/api/v1/line/subscription",json={"enabled":True,"consent_version":CONSENT_VERSION})
    assert response.json()["ready"] is True
    assert sub.consented_at and sub.consent_version==CONSENT_VERSION
    assert await recipient_eligible(db_session,UID)
    with patch("app.api.v1.line_onboarding.line_friendship",AsyncMock(side_effect=RuntimeError("must not call"))):
        response=await client.put("/api/v1/line/subscription",json={"enabled":False})
    assert response.json()["ready"] is False
    assert not await recipient_eligible(db_session,UID)

@pytest.mark.asyncio
async def test_location_is_bound_to_verified_identity(client,identity,db_session):
    geocoder=SimpleNamespace(reverse=AsyncMock(return_value=SimpleNamespace(province="Bangkok",district="Test",subdistrict="Test",country_code="TH")))
    app.dependency_overrides[get_reverse_geocoder]=lambda:geocoder
    response=await client.post("/api/v1/line/location/from-gps",json={"latitude":13.7563,"longitude":100.5018})
    assert response.status_code==200
    assert response.json()["external_user_id"]==UID
    sub=await db_session.get(LineSubscription,UID)
    assert sub.verified_location_id==response.json()["location"]["id"]
    assert not sub.enabled

@pytest.mark.asyncio
async def test_spoofed_identity_is_not_an_input(client,identity):
    response=await client.put("/api/v1/line/subscription",json={"enabled":False,"external_user_id":"Uother"})
    assert response.status_code==422

@pytest.mark.asyncio
async def test_block_clears_consent_enable_on_status(client,identity,db_session):
    user,location=await area(db_session);sub=await record(db_session,user,location,consent_version=CONSENT_VERSION)
    sub.enabled=True;await db_session.flush()
    with patch("app.api.v1.line_onboarding.line_friendship",AsyncMock(return_value=False)):
        response=await client.get("/api/v1/line/onboarding")
    assert response.json()["next_step"]=="friend"
    assert not sub.enabled and not sub.friend

@pytest.mark.asyncio
async def test_webhook_block_follow_and_out_of_order(client,enabled,db_session):
    user,location=await area(db_session);sub=await record(db_session,user,location,consent_version=CONSENT_VERSION)
    sub.enabled=True;await db_session.flush()
    async def event(kind,timestamp,signature=True):
        body=json.dumps({"events":[{"type":kind,"timestamp":timestamp,"source":{"type":"user","userId":UID}}]}).encode()
        digest=base64.b64encode(hmac.new(b"test-secret",body,hashlib.sha256).digest()).decode()
        return await client.post("/api/v1/line/webhook",content=body,headers={"x-line-signature":digest if signature else "bad","content-type":"application/json"})
    assert (await event("unfollow",20,False)).status_code==400
    assert sub.enabled
    assert (await event("unfollow",20)).status_code==200
    assert not sub.enabled and not sub.friend
    await event("follow",30)
    assert sub.friend and not sub.enabled
    await event("unfollow",20)
    assert sub.friend and sub.friend_event_time==30

@pytest.mark.asyncio
async def test_recipient_discovery_excludes_unsubscribed_browser_and_changed_location(identity,db_session):
    user,location=await area(db_session);sub=await record(db_session,user,location,consent_version=CONSENT_VERSION)
    sub.enabled=True
    db_session.add(User(external_id="browser-test",current_location_id=location.id))
    db_session.add(User(external_id="U-not-subscribed",current_location_id=location.id));await db_session.flush()
    ids=list((await db_session.scalars(select(User.external_id).where(recipient_condition()))).all())
    assert ids==[UID]
    sub.verified_location_id=None;await db_session.flush()
    assert not await recipient_eligible(db_session,UID)

@pytest.mark.asyncio
@pytest.mark.parametrize("suffix,method", [("/forecast","get"),("/forecast/refresh","post"),("/location/from-gps","post")])
async def test_legacy_line_paths_require_matching_identity(client,enabled,suffix,method):
    with patch("app.services.line_identity.verify_line_token",AsyncMock(return_value=LineIdentity(UID,"token"))):
        response=await getattr(client,method)("/api/v1/users/Uother"+suffix,headers={"Authorization":"Bearer token"},json={"latitude":13,"longitude":100} if "location" in suffix else None) if method=="post" else await client.get("/api/v1/users/Uother"+suffix,headers={"Authorization":"Bearer token"})
    assert response.status_code==403

class FakeClient:
    def __init__(self,verified,subject=UID):self.verified,self.subject=verified,subject
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def get(self,path,**kwargs):
        return httpx.Response(200,json=self.verified if path.endswith("/verify") else {"sub":self.subject})

@pytest.mark.asyncio
@pytest.mark.parametrize("data",[
 {"client_id":"wrong","expires_in":10,"scope":"openid profile"},
 {"client_id":"123","expires_in":0,"scope":"openid profile"},
 {"client_id":"123","expires_in":10,"scope":"openid"},
 {"client_id":"123","expires_in":"10","scope":"openid profile"}])
async def test_access_token_channel_expiry_and_scopes(enabled,data):
    from fastapi import HTTPException
    with patch("app.services.line_identity.httpx.AsyncClient",return_value=FakeClient(data)):
        with pytest.raises(HTTPException) as error:await verify_line_token("token")
    assert error.value.status_code==401

@pytest.mark.asyncio
async def test_valid_verified_access_token(enabled):
    with patch("app.services.line_identity.httpx.AsyncClient",return_value=FakeClient({"client_id":"123","expires_in":10,"scope":"openid profile"})):
        identity=await verify_line_token("token")
    assert identity.user_id==UID

@pytest.mark.asyncio
async def test_invalid_coordinates_rejected(client,identity):
    assert (await client.post("/api/v1/line/location/from-gps",json={"latitude":91,"longitude":100})).status_code==422

def test_access_token_logging_is_redacted_and_status_format_preserved():
    import logging
    from app.services.line_identity import _RedactAccessToken
    item=logging.LogRecord("httpx",logging.INFO,"test",1,
        'HTTP Request: %s %s "%s %d %s"',
        ("GET","https://api.line.me/oauth2/v2.1/verify?access_token=secret-sensitive-token&x=1","HTTP/1.1",200,"OK"),None)
    assert _RedactAccessToken().filter(item)
    message=item.getMessage()
    assert "secret-sensitive-token" not in message
    assert "access_token=[REDACTED]&x=1" in message
    assert "200 OK" in message

@pytest.mark.asyncio
@pytest.mark.parametrize("missing",["LINE_CHANNEL_ACCESS_TOKEN","LINE_CHANNEL_SECRET","LINE_LOGIN_CHANNEL_ID","LINE_OFFICIAL_ACCOUNT_ID"])
async def test_signup_does_not_claim_available_with_missing_configuration(client,identity,monkeypatch,missing):
    monkeypatch.setattr(settings,missing,None)
    assert (await client.get("/api/v1/line/onboarding/config")).json()["enabled"] is False
    assert (await client.get("/api/v1/line/onboarding")).status_code==503

def test_settings_require_all_signup_dependencies():
    from app.core.config import Settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None,LINE_SUBSCRIPTIONS_ENABLED=True,LINE_LOGIN_CHANNEL_ID=None,LINE_CHANNEL_ACCESS_TOKEN=None,LINE_CHANNEL_SECRET=None,LINE_OFFICIAL_ACCOUNT_ID=None)
    configured=Settings(_env_file=None,LINE_SUBSCRIPTIONS_ENABLED=True,LINE_LOGIN_CHANNEL_ID="123",LINE_CHANNEL_ACCESS_TOKEN="mock-token",LINE_CHANNEL_SECRET="mock-secret",LINE_OFFICIAL_ACCOUNT_ID="@weather")
    assert configured.LINE_SUBSCRIPTIONS_ENABLED

@pytest.mark.asyncio
@pytest.mark.parametrize("consent_ms,enabled_after",[(1000,False),(4000,True)])
async def test_late_block_event_respects_newer_explicit_consent(client,identity,db_session,consent_ms,enabled_after):
    from app.api.v1.line_onboarding import apply_friend_events
    user,location=await area(db_session)
    sub=await record(db_session,user,location,consent_version=CONSENT_VERSION)
    sub.enabled=True
    sub.consented_at=datetime.fromtimestamp(consent_ms/1000,timezone.utc)
    sub.friend_event_time=3000
    await db_session.flush()
    await apply_friend_events(db_session,[{"type":"unfollow","timestamp":2000,"source":{"type":"user","userId":UID}}])
    assert sub.friend is True and sub.friend_event_time==3000
    assert sub.enabled is enabled_after

@pytest.mark.asyncio
@pytest.mark.parametrize("consent_ms,enabled_after",[(1000,False),(4000,True)])
async def test_follow_cannot_keep_old_consent_but_preserves_new_confirmation(client,identity,db_session,consent_ms,enabled_after):
    from app.api.v1.line_onboarding import apply_friend_events
    user,location=await area(db_session)
    sub=await record(db_session,user,location,consent_version=CONSENT_VERSION)
    sub.enabled=True
    sub.consented_at=datetime.fromtimestamp(consent_ms/1000,timezone.utc)
    await db_session.flush()
    await apply_friend_events(db_session,[{"type":"follow","timestamp":2000,"source":{"type":"user","userId":UID}}])
    assert sub.friend is True
    assert sub.enabled is enabled_after
