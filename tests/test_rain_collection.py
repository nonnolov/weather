"""P2 collection tests; real PostgreSQL only in the isolated local fixture."""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone

import httpx
import pytest
from sqlalchemy import func,select
from sqlalchemy.exc import IntegrityError
from app.core.config import Settings,settings
from app.evaluation.rain_collection import (
    CollectionResult,run_collection_cycle,rain_collection_lifespan,station_status,
)
from app.evaluation.rain_evidence import stage_station
from app.models.rain_station_fetch import RainStationFetch
from app.models.notification import NotificationDelivery
from tests.test_rain_locking_postgres import pg_sessions
from tests.test_rain_evidence_postgres import pg_schema

NOW=datetime(2026,10,11,0,tzinfo=timezone.utc)

def bundle(amount=0,collected=NOW):
    body=json.dumps({"result":"OK","data":[
        {"rainfall_datetime":"2026-10-11 06:00","rainfall_value":amount},
        {"rainfall_datetime":"2026-10-11 07:00","rainfall_value":None}]})
    return stage_station(json.loads(body),body.encode(),collected_at=collected),body

def forbid_line(monkeypatch):
    async def forbidden(*args,**kwargs):
        raise AssertionError("P2 must never send LINE")
    monkeypatch.setattr("app.notifications.line_client.LineClient.push_text",forbidden)

@pytest.mark.asyncio
async def test_disabled_cycle_and_lifespan_do_no_work(monkeypatch):
    monkeypatch.setattr(settings,"P2_RAIN_COLLECTION_ENABLED",False)
    assert (await run_collection_cycle(None)).status=="disabled"
    async with rain_collection_lifespan(None):
        pass

def test_collection_default_is_disabled():
    assert Settings(_env_file=None).P2_RAIN_COLLECTION_ENABLED is False

@pytest.mark.asyncio
async def test_collection_requires_explicit_postgres_factory(monkeypatch):
    monkeypatch.setattr(settings,"P2_RAIN_COLLECTION_ENABLED",True)
    with pytest.raises(ValueError):
        await run_collection_cycle(None)

@pytest.mark.asyncio
async def test_success_dedupe_hourly_due_and_preserved_corrections(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"P2_RAIN_COLLECTION_ENABLED",True)
    forbid_line(monkeypatch)
    calls=[]
    async def fetch(clock):
        calls.append(clock())
        return bundle(amount=len(calls)-1,collected=clock())
    first=await run_collection_cycle(pg_sessions,clock=lambda:NOW,fetch=fetch)
    assert first==CollectionResult("quarantined",1,1)
    assert (await run_collection_cycle(pg_sessions,clock=lambda:NOW+timedelta(minutes=1),fetch=fetch)).status=="already_collected"
    # First fetch at 00:00; an entirely new hour is required.
    second=await run_collection_cycle(pg_sessions,clock=lambda:NOW+timedelta(hours=1),fetch=fetch)
    assert second.status=="quarantined" and len(calls)==2
    async with pg_sessions() as db:
        rows=list((await db.scalars(select(RainStationFetch).order_by(RainStationFetch.id))).all())
        assert len(rows)==2
        assert rows[0].evidence["rows"][0]["raw_rainfall_value"]==0
        assert rows[1].evidence["rows"][0]["raw_rainfall_value"]==1
        assert all(not row.evidence["evaluation_eligible"] for row in rows)
        assert await db.scalar(select(func.count()).select_from(NotificationDelivery))==1
        report=await station_status(db)
        assert report["known_rows"]==1 and report["missing_rows"]==1
        assert report["eligible_pairs"]==0 and report["metrics"] is None
        assert not report["alignment_verified"] and not report["accuracy_claim_available"]

@pytest.mark.asyncio
async def test_moving_across_hour_boundary_cannot_poll_early(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"P2_RAIN_COLLECTION_ENABLED",True)
    async def fetch(clock):return bundle(collected=clock())
    clock=NOW+timedelta(minutes=50)
    await run_collection_cycle(pg_sessions,clock=lambda:clock,fetch=fetch)
    assert (await run_collection_cycle(pg_sessions,clock=lambda:NOW+timedelta(hours=1),fetch=fetch)).status=="not_due"

@pytest.mark.asyncio
async def test_concurrent_replica_skips_without_extra_request(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"P2_RAIN_COLLECTION_ENABLED",True)
    started,release=asyncio.Event(),asyncio.Event()
    calls=[]
    async def fetch(clock):
        calls.append(1);started.set()
        await release.wait()
        return bundle(collected=clock())
    task=asyncio.create_task(run_collection_cycle(pg_sessions,clock=lambda:NOW,fetch=fetch))
    try:
        await asyncio.wait_for(started.wait(),5)
        assert (await run_collection_cycle(pg_sessions,clock=lambda:NOW,fetch=fetch)).status=="busy"
    finally:
        release.set()
    assert (await task).status=="quarantined" and len(calls)==1

@pytest.mark.asyncio
@pytest.mark.parametrize("kind,code",[
    ("http","provider_http_error"),("network","provider_network_error"),("schema","provider_contract_error"),
])
async def test_provider_failure_is_durable_and_sanitized(pg_sessions,monkeypatch,kind,code):
    monkeypatch.setattr(settings,"P2_RAIN_COLLECTION_ENABLED",True)
    forbid_line(monkeypatch)
    async def fetch(clock):
        if kind=="http":
            req=httpx.Request("GET","https://example.test/?secret=private")
            raise httpx.HTTPStatusError("private detail",request=req,response=httpx.Response(503,request=req))
        if kind=="network":
            raise httpx.ConnectError("private network detail")
        raise ValueError("private parsing detail")
    assert (await run_collection_cycle(pg_sessions,clock=lambda:NOW,fetch=fetch)).status=="failed"
    assert (await run_collection_cycle(pg_sessions,clock=lambda:NOW,fetch=fetch)).status=="already_collected"
    async with pg_sessions() as db:
        row=await db.scalar(select(RainStationFetch))
        assert row.error_code==code and row.evidence is None and row.raw_body is None
        assert row.raw_sha256 is None
        assert (await station_status(db))["status"]=="collection_failed"

@pytest.mark.asyncio
async def test_cancelled_fetch_rolls_back_and_releases_collector_lock(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"P2_RAIN_COLLECTION_ENABLED",True)
    entered=asyncio.Event()
    async def never(clock):
        entered.set()
        await asyncio.Event().wait()
    task=asyncio.create_task(run_collection_cycle(pg_sessions,clock=lambda:NOW,fetch=never))
    await asyncio.wait_for(entered.wait(),5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    async with pg_sessions() as db:
        assert await db.scalar(select(func.count()).select_from(RainStationFetch))==0
    async def good(clock):return bundle(collected=clock())
    assert (await run_collection_cycle(pg_sessions,clock=lambda:NOW,fetch=good)).status=="quarantined"

@pytest.mark.asyncio
async def test_unique_poll_slot_is_enforced_by_database(pg_sessions):
    async with pg_sessions() as db:
        for _ in range(2):
            db.add(RainStationFetch(station_id=1116457,poll_slot=NOW,
                collected_at=NOW,status="failed",error_code="provider_network_error"))
        with pytest.raises(IntegrityError):
            await db.commit()

@pytest.mark.asyncio
async def test_status_read_does_not_fetch_or_send_line(client,monkeypatch):
    forbid_line(monkeypatch)
    async def forbidden(*args,**kwargs):raise AssertionError("Status GET must not fetch")
    monkeypatch.setattr("app.evaluation.rain_collection.fetch_station",forbidden)
    response=await client.get("/api/v1/rain-reference/status")
    assert response.status_code==200
    body=response.json()
    assert body["status"]=="no_fetches" and body["metrics"] is None
    assert body["eligible_pairs"]==0 and not body["accuracy_claim_available"]

@pytest.mark.asyncio
async def test_existing_lifespan_and_new_collector_are_both_preserved(monkeypatch):
    import app.main as main
    events=[]
    @asynccontextmanager
    async def first(app):
        events.append("p1-enter")
        try:yield
        finally:events.append("p1-exit")
    @asynccontextmanager
    async def second(app):
        events.append("p2-enter")
        try:yield
        finally:events.append("p2-exit")
    monkeypatch.setattr(main,"scheduled_preview_lifespan",first)
    monkeypatch.setattr(main,"rain_collection_lifespan",second)
    async with main.application_lifespan(None):
        events.append("serve")
    assert events==["p1-enter","p2-enter","serve","p2-exit","p1-exit"]

def test_migration_0008_is_additive_and_constraints_hold(pg_schema):
    engine,_,_,migrate=pg_schema
    import sqlalchemy as sa
    migrate("0007")
    with engine.begin() as db:
        db.execute(sa.text("INSERT INTO locations (id,name,slug,latitude,longitude,created_at,updated_at) VALUES (1,'baseline','p203',0,0,:now,:now)"),{"now":NOW})
        before=db.execute(sa.text("SELECT count(*) FROM locations")).scalar_one()
    migrate("0008")
    with engine.begin() as db:
        assert db.execute(sa.text("SELECT count(*) FROM locations")).scalar_one()==before
        db.execute(sa.text("INSERT INTO rain_station_fetches (station_id,poll_slot,collected_at,status) VALUES (1116457,:now,:now,'quarantined')"),{"now":NOW})
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as db:
            db.execute(sa.text("INSERT INTO rain_station_fetches (station_id,poll_slot,collected_at,status) VALUES (1116457,:now,:now,'quarantined')"),{"now":NOW})
    migrate("0007",downgrade=True)
    with engine.connect() as db:
        assert db.execute(sa.text("SELECT count(*) FROM locations")).scalar_one()==before
    migrate("0008")


@pytest.mark.asyncio
@pytest.mark.parametrize("case",["valid","http_failure","oversize","bad_schema"])
async def test_streamed_fetch_contract_and_size_bound(monkeypatch,case):
    from app.evaluation import rain_collection as module
    real_client=httpx.AsyncClient
    body=json.dumps({"result":"OK","data":[
        {"rainfall_datetime":"2026-10-11 07:00","rainfall_value":0}]}).encode()
    if case=="bad_schema":
        body=b'{"result":"ERROR","data":[]}'
    def handler(request):
        assert str(request.url)==module.ENDPOINT+"?station_id=1116457"
        return httpx.Response(503 if case=="http_failure" else 200,content=body)
    def factory(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return real_client(transport=httpx.MockTransport(handler),**kwargs)
    monkeypatch.setattr(module.httpx,"AsyncClient",factory)
    if case=="oversize":
        monkeypatch.setattr(module,"MAX_BODY_BYTES",10)
    if case=="valid":
        import hashlib
        evidence,raw=await module.fetch_station(lambda:NOW)
        assert raw.encode()==body
        assert evidence["raw_sha256"]==hashlib.sha256(body).hexdigest()
        assert evidence["known_rows"]==1 and not evidence["evaluation_eligible"]
    else:
        with pytest.raises(httpx.HTTPStatusError if case=="http_failure" else ValueError):
            await module.fetch_station(lambda:NOW)
