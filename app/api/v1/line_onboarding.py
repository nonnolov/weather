from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StrictBool
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.line_subscription import LineSubscription
from app.models.location import Location
from app.schemas.location import LocationFromGps
from app.schemas.user import UserLocationRead
from app.schemas.forecast import ForecastRunDetail, IngestResponse
from app.services.line_identity import LineIdentity, require_line_identity, line_friendship
from app.services.geocoding import ReverseGeocoder, get_reverse_geocoder
from app.notifications.subscriptions import CONSENT_VERSION
from app.api.v1.users import set_user_location_from_gps, get_user_forecast, refresh_user_forecast
router = APIRouter()

def configured():
    return bool(settings.LINE_LOGIN_CHANNEL_ID and settings.LINE_CHANNEL_ACCESS_TOKEN and settings.LINE_CHANNEL_SECRET and settings.LINE_OFFICIAL_ACCOUNT_ID)

def feature_enabled(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    if not settings.LINE_SUBSCRIPTIONS_ENABLED or not configured():
        raise HTTPException(503, "LINE notification signup is not available yet.")

class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    consent_version: str | None = None

async def locked_user(db, user_id):
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtext("line-onboarding:" + user_id))))
    user = await db.scalar(select(User).where(User.external_id == user_id).with_for_update())
    if user is None:
        user = User(external_id=user_id)
        db.add(user)
        await db.flush()
    return user

async def subscription(db, user_id, create=False):
    record = await db.scalar(select(LineSubscription).where(LineSubscription.user_id == user_id).with_for_update())
    if record is None and create:
        record = LineSubscription(user_id=user_id, enabled=False, friend=False, updated_at=datetime.now(timezone.utc), friend_event_time=0)
        db.add(record)
        await db.flush()
    return record

async def state(db, user, record, friend):
    location = await db.get(Location, user.current_location_id) if user.current_location_id else None
    verified = bool(record and location and location.is_active and record.verified_location_id == location.id)
    enabled = bool(record and record.enabled)
    ready = bool(enabled and friend and verified and record.consent_version == CONSENT_VERSION)
    return {"external_user_id": user.external_id, "friend": friend, "location_verified": verified,
            "location_id": location.id if verified else None, "enabled": enabled, "ready": ready,
            "consent_version": CONSENT_VERSION,
            "next_step": "ready" if ready else "friend" if not friend else "location" if not verified else "consent"}

@router.get("/onboarding/config")
async def onboarding_config():
    account = settings.LINE_OFFICIAL_ACCOUNT_ID
    return {"enabled": settings.LINE_SUBSCRIPTIONS_ENABLED and configured(),
            "add_friend_url": "https://line.me/R/ti/p/" + quote(account, safe="") if account else None}

@router.get("/onboarding", dependencies=[Depends(feature_enabled)])
async def onboarding_status(identity: LineIdentity = Depends(require_line_identity), db: AsyncSession = Depends(get_db)):
    user = await locked_user(db, identity.user_id)
    friend = await line_friendship(identity)
    record = await subscription(db, identity.user_id)
    if record:
        record.friend = friend
        if not friend:
            record.enabled = False
        record.updated_at = datetime.now(timezone.utc)
    return await state(db, user, record, friend)

@router.put("/subscription", dependencies=[Depends(feature_enabled)])
async def update_subscription(payload: SubscriptionUpdate, identity: LineIdentity = Depends(require_line_identity), db: AsyncSession = Depends(get_db)):
    # Disabling must still work if the friendship service is down.
    user = await locked_user(db, identity.user_id)
    friend = await line_friendship(identity) if payload.enabled else None
    record = await subscription(db, identity.user_id, create=True)
    if payload.enabled:
        if not friend:
            record.friend = False
            record.enabled = False
            await db.flush()
            return JSONResponse({"detail": "Add or unblock Weather in LINE first."}, status_code=409, headers={"Cache-Control":"no-store"})
        location = await db.get(Location, user.current_location_id) if user.current_location_id else None
        if not location or not location.is_active or record.verified_location_id != location.id:
            raise HTTPException(409, "Set your notification location first.")
        if payload.consent_version != CONSENT_VERSION:
            raise HTTPException(422, "Confirm the current notification consent.")
        record.friend = True
        record.enabled = True
        record.consent_version = CONSENT_VERSION
        record.consented_at = datetime.now(timezone.utc)
    else:
        record.enabled = False
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await state(db, user, record, record.friend)

@router.post("/location/from-gps", response_model=UserLocationRead, dependencies=[Depends(feature_enabled)])
async def verified_location(payload: LocationFromGps, identity: LineIdentity = Depends(require_line_identity), db: AsyncSession = Depends(get_db), geocoder: ReverseGeocoder = Depends(get_reverse_geocoder)):
    await locked_user(db, identity.user_id)
    result = await set_user_location_from_gps(payload, identity.user_id, db, geocoder)
    record = await subscription(db, identity.user_id, create=True)
    record.verified_location_id = result.location.id
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return result

@router.get("/forecast", response_model=ForecastRunDetail, dependencies=[Depends(feature_enabled)])
async def own_forecast(identity: LineIdentity = Depends(require_line_identity), db: AsyncSession = Depends(get_db)):
    return await get_user_forecast(identity.user_id, db)

@router.post("/forecast/refresh", response_model=IngestResponse, status_code=201, dependencies=[Depends(feature_enabled)])
async def own_refresh(identity: LineIdentity = Depends(require_line_identity), db: AsyncSession = Depends(get_db)):
    return await refresh_user_forecast(identity.user_id, 7, db)

async def apply_friend_events(db, events):
    for event in events:
        if not isinstance(event, dict):
            continue
        source = event.get("source") or {}
        if not isinstance(source, dict):
            continue
        user_id, kind, stamp = source.get("userId"), event.get("type"), event.get("timestamp")
        if source.get("type") != "user" or kind not in ("follow", "unfollow") or not isinstance(user_id, str) or not user_id.startswith("U") or type(stamp) is not int or stamp <= 0:
            continue
        await locked_user(db, user_id)
        record = await subscription(db, user_id, create=True)
        consented = record.consented_at
        if consented is not None and consented.tzinfo is None:
            consented = consented.replace(tzinfo=timezone.utc)
        consent_time = int(consented.timestamp() * 1000) if consented else 0
        # Membership changes revoke earlier consent even when their webhook
        # arrives after a newer friendship event. Later explicit consent wins.
        if record.enabled and stamp >= consent_time:
            record.enabled = False
            record.updated_at = datetime.now(timezone.utc)
        if stamp <= record.friend_event_time:
            continue
        record.friend_event_time = stamp
        record.friend = kind == "follow"
        # Follow/unblock never grants or restores notification consent.
        record.updated_at = datetime.now(timezone.utc)
    await db.flush()
