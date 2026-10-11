"""Real concurrent tests against a disposable local PostgreSQL schema only."""
import asyncio
import os
from uuid import uuid4
from datetime import timedelta
import pytest
import pytest_asyncio
from sqlalchemy import text, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.database import Base
from app.core.config import settings
from app.ingestion.fetch_control import fetch_shared_forecast, reserve_requests, ForecastControlError
from app.models.forecast_fetch import ProviderRequestBudget
from tests.test_forecast_fetch_control import NOW,location,provider
from app.models.location import Location
from app.ingestion.service import ingest_forecast_for_location
from datetime import datetime, timezone

URL=os.environ.get("FETCH_CONTROL_TEST_POSTGRES_URL")
pytestmark=pytest.mark.skipif(not URL,reason="Disposable localhost FETCH_CONTROL_TEST_POSTGRES_URL required")


@pytest_asyncio.fixture
async def pg_sessions():
    url=make_url(URL)
    assert url.host=="127.0.0.1" and url.port==55439 and url.username=="forecast_control_test" and url.database=="postgres" and not url.query
    schema="fetch_control_test_"+uuid4().hex
    admin=create_async_engine(url,poolclass=NullPool)
    async with admin.begin() as conn:
        assert 160000<=int(await conn.scalar(text("SHOW server_version_num")))<170000
        await conn.execute(text('CREATE SCHEMA "'+schema+'"'))
    engine=create_async_engine(url,poolclass=NullPool,connect_args={"server_settings":{"search_path":schema}})
    try:
        async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine,expire_on_commit=False,autoflush=False)
    finally:
        await engine.dispose()
        async with admin.begin() as conn:await conn.execute(text('DROP SCHEMA "'+schema+'" CASCADE'))
        await admin.dispose()


@pytest.mark.asyncio
async def test_parallel_locations_call_provider_once(pg_sessions):
    p=provider()
    entered=asyncio.Event();release=asyncio.Event()
    result=p.fetch_forecast.return_value
    async def fetch(**kwargs):
        entered.set();await release.wait();return result
    p.fetch_forecast.side_effect=fetch
    first=asyncio.create_task(fetch_shared_forecast(location(),7,p,pg_sessions,clock=lambda:NOW))
    await asyncio.wait_for(entered.wait(),5)
    second=asyncio.create_task(fetch_shared_forecast(location(13.264470,100.925995),7,p,pg_sessions,clock=lambda:NOW))
    release.set()
    a,b=await asyncio.wait_for(asyncio.gather(first,second),10)
    assert p.fetch_forecast.await_count==1
    assert a.hourly==b.hourly and a.retrieved_at==b.retrieved_at==NOW


@pytest.mark.asyncio
async def test_concurrent_quota_never_exceeds_budget(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_MONTHLY_LIMIT",5)
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_DAILY_LIMIT",5)
    results=await asyncio.gather(*(reserve_requests(pg_sessions,"google_weather",1,now=NOW) for _ in range(12)),return_exceptions=True)
    assert sum(v is None for v in results)==5
    assert sum(isinstance(v,ForecastControlError) for v in results)==7
    async with pg_sessions() as db:
        row=await db.get(ProviderRequestBudget,("google_weather","m:2026-10"))
        assert row.reserved==5


@pytest.mark.asyncio
async def test_caller_rollback_does_not_refund_or_erase_fetch(pg_sessions):
    p=provider()
    first=await fetch_shared_forecast(location(),7,p,pg_sessions,clock=lambda:NOW)
    async with pg_sessions() as caller:await caller.rollback()
    second=await fetch_shared_forecast(location(),7,p,pg_sessions,clock=lambda:NOW+timedelta(minutes=1))
    assert p.fetch_forecast.await_count==1 and second.retrieved_at==first.retrieved_at
    async with pg_sessions() as db:
        assert (await db.get(ProviderRequestBudget,("open_meteo","m:2026-10"))).reserved==1


@pytest.mark.asyncio
async def test_ingestion_shares_fetch_but_preserves_location_snapshots(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"FORECAST_SHARING_ENABLED",True)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal",pg_sessions)
    p=provider()
    p.fetch_forecast.return_value.retrieved_at=datetime.now(timezone.utc)
    monkeypatch.setattr("app.ingestion.service.get_provider",lambda name:p)
    async with pg_sessions() as db:
        a=Location(name="a",slug="gps-location-a",latitude=13.264196,longitude=100.926522,timezone="Asia/Bangkok",provider="open_meteo")
        b=Location(name="b",slug="gps-location-b",latitude=13.264470,longitude=100.925995,timezone="Asia/Bangkok",provider="open_meteo")
        db.add_all([a,b]);await db.commit()
        first=await ingest_forecast_for_location(db,a,7);await db.commit()
        second=await ingest_forecast_for_location(db,b,7);await db.commit()
        repeated=await ingest_forecast_for_location(db,b,7)
        assert p.fetch_forecast.await_count==1
        assert first.location_id==a.id and second.location_id==b.id
        assert first.id!=second.id and second.id==repeated.id
        assert first.retrieved_at==second.retrieved_at
