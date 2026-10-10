"""Durable hourly station collection, quarantined until the feed contract is verified."""
import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager,suppress
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone

import httpx
from sqlalchemy import func,select,text
from sqlalchemy.ext.asyncio import AsyncEngine,async_sessionmaker

from app.core.config import settings
from app.evaluation.rain_evidence import ENDPOINT,STATION_ID,stage_station
from app.models.rain_station_fetch import RainStationFetch

logger=logging.getLogger(__name__)
COLLECTION_LOCK_KEY=57869370623934002
POLL_SECONDS=3600
STARTUP_DELAY_SECONDS=90
MAX_BODY_BYTES=2_000_000

@dataclass(frozen=True)
class CollectionResult:
    status: str
    known_rows: int=0
    missing_rows: int=0

def utc(value):
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc))

def validate_factory(sessions):
    if not isinstance(sessions,async_sessionmaker):
        raise ValueError("Engine-bound PostgreSQL factory required")
    engine=sessions.kw.get("bind")
    if not isinstance(engine,AsyncEngine) or engine.dialect.name!="postgresql":
        raise ValueError("Engine-bound PostgreSQL factory required")

async def fetch_station(clock):
    # Streaming enforces the byte cap before loading or parsing a response.
    async with httpx.AsyncClient(timeout=15,follow_redirects=False,trust_env=False) as client:
        async with client.stream("GET",ENDPOINT,params={"station_id":STATION_ID}) as response:
            response.raise_for_status()
            chunks=[];size=0
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>MAX_BODY_BYTES:
                    raise ValueError("station_response_too_large")
                chunks.append(chunk)
    body=b"".join(chunks)
    import json
    evidence=stage_station(json.loads(body),body,collected_at=clock())
    # UTF-8 is required by this feed; preserve exact bytes through text storage.
    raw_text=body.decode("utf-8")
    assert hashlib.sha256(raw_text.encode("utf-8")).hexdigest()==evidence["raw_sha256"]
    return evidence,raw_text

async def run_collection_cycle(sessions,*,clock=lambda:datetime.now(timezone.utc),fetch=fetch_station):
    if not settings.P2_RAIN_COLLECTION_ENABLED:
        return CollectionResult("disabled")
    validate_factory(sessions)
    try:
        async with asyncio.timeout(35):
            async with sessions() as db:
                async with db.begin():
                    await db.execute(text("SELECT set_config('statement_timeout','5000ms',true)"))
                    if not await db.scalar(select(func.pg_try_advisory_xact_lock(COLLECTION_LOCK_KEY))):
                        return CollectionResult("busy")
                    now=utc(clock())
                    slot=now.replace(minute=0,second=0,microsecond=0)
                    existing=await db.scalar(select(RainStationFetch.id).where(
                        RainStationFetch.station_id==STATION_ID,RainStationFetch.poll_slot==slot))
                    if existing is not None:
                        return CollectionResult("already_collected")
                    latest=await db.scalar(select(func.max(RainStationFetch.collected_at)).where(
                        RainStationFetch.station_id==STATION_ID))
                    if latest is not None and now-utc(latest)<timedelta(hours=1):
                        return CollectionResult("not_due")
                    evidence=raw_body=None;error=None
                    try:
                        evidence,raw_body=await fetch(clock)
                    except httpx.HTTPStatusError:
                        error="provider_http_error"
                    except httpx.RequestError:
                        error="provider_network_error"
                    except (ValueError,UnicodeError,TypeError,KeyError):
                        error="provider_contract_error"
                    row=RainStationFetch(station_id=STATION_ID,poll_slot=slot,
                        collected_at=utc(clock()),status="failed" if error else "quarantined",
                        error_code=error,raw_sha256=evidence["raw_sha256"] if evidence else None,
                        raw_body=raw_body,evidence=evidence)
                    db.add(row)
                result=CollectionResult(row.status,
                    evidence["known_rows"] if evidence else 0,evidence["missing_rows"] if evidence else 0)
    except TimeoutError:
        result=CollectionResult("timeout")
    except Exception:
        result=CollectionResult("error")
    logger.info("P2 station collection: status=%s known_rows=%s missing_rows=%s",
                result.status,result.known_rows,result.missing_rows)
    return result

async def station_status(db):
    # Bounded reads: indexed latest success plus one latest attempt.
    latest=await db.scalar(select(RainStationFetch).where(RainStationFetch.station_id==STATION_ID)
        .order_by(RainStationFetch.collected_at.desc(),RainStationFetch.id.desc()).limit(1))
    success=await db.scalar(select(RainStationFetch).where(RainStationFetch.station_id==STATION_ID,
        RainStationFetch.status=="quarantined")
        .order_by(RainStationFetch.collected_at.desc(),RainStationFetch.id.desc()).limit(1))
    evidence=success.evidence if success else None
    return {"collection_enabled":settings.P2_RAIN_COLLECTION_ENABLED,
        "station_id":STATION_ID,
        "status":"pending_contract_verification" if success else ("collection_failed" if latest else "no_fetches"),
        "latest_attempt_at":utc(latest.collected_at).isoformat() if latest else None,
        "latest_attempt_status":latest.status if latest else None,
        "latest_error_code":latest.error_code if latest else None,
        "latest_success_at":utc(success.collected_at).isoformat() if success else None,
        "latest_success_stale":bool(success and datetime.now(timezone.utc)-utc(success.collected_at)>timedelta(hours=2)),
        "known_rows":evidence["known_rows"] if evidence else 0,
        "missing_rows":evidence["missing_rows"] if evidence else 0,
        "invalid_rows":evidence["invalid_rows"] if evidence else 0,
        "alignment_verified":False,"station_is_at_user_point":False,
        "eligible_pairs":0,"metrics":None,"accuracy_claim_available":False,
        "blocked_by":evidence["blocked_by"] if evidence else ["no_usable_station_fetch"],
        "limitations":["Nearby station data are distinct from point observations.",
            "Endpoint timezone and accumulation interval still require authoritative confirmation.",
            "Known rows are provider values, not verified instrument quality or eligible pairs."]}

async def serve(sessions):
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        await run_collection_cycle(sessions)
        await asyncio.sleep(POLL_SECONDS)

@asynccontextmanager
async def rain_collection_lifespan(app):
    if not settings.P2_RAIN_COLLECTION_ENABLED:
        yield
        return
    from app.core.database import AsyncSessionLocal
    validate_factory(AsyncSessionLocal)
    task=asyncio.create_task(serve(AsyncSessionLocal),name="rain-reference-collector")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
