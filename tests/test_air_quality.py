import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
import httpx
import pytest
from app.services import air_quality as aq
from app.models.location import Location

NOW = datetime(2026, 10, 10, 17, 30, tzinfo=timezone.utc)
def payload():
    start = int(NOW.replace(minute=0).timestamp())
    return {"utc_offset_seconds": 0, "hourly_units": {"time": "unixtime", "pm2_5": "μg/m³", "european_aqi": "EAQI"},
            "hourly": {"time": [start + 3600*i for i in range(-1,25)],
                       "pm2_5": [10.0]*26, "european_aqi": [30.0]*26}}

@pytest.mark.parametrize("value,expected", [(0,"good"),(20,"good"),(20.1,"fair"),(40,"fair"),(40.1,"moderate"),(60,"moderate"),(60.1,"poor"),(80,"poor"),(80.1,"very_poor"),(100,"very_poor"),(100.1,"extremely_poor"),(None,None)])
def test_aqi_boundaries(value,expected):
    assert aq.level(value)==expected

@pytest.mark.parametrize("value", [None,-1,float("nan"),float("inf"),True,"10",{},[]])
def test_invalid_values_missing_not_zero(value):
    data=payload();data["hourly"]["pm2_5"][1]=value
    report=aq.render(aq.normalize(data,NOW),NOW)
    assert report["current"]["pm25"] is None
    assert report["current"]["aqi"]==30
    assert report["measurement_available"] is False

@pytest.mark.parametrize("mutation", ["offset","pm_unit","aqi_unit","time_unit","length","duplicate","unsorted","naive","boolean_time","too_many"])
def test_bad_contract_rejected(mutation):
    data=payload();clock=NOW
    if mutation=="offset":data["utc_offset_seconds"]=25200
    if mutation=="pm_unit":data["hourly_units"]["pm2_5"]="mg/m³"
    if mutation=="aqi_unit":data["hourly_units"]["european_aqi"]="USAQI"
    if mutation=="time_unit":data["hourly_units"]["time"]="iso8601"
    if mutation=="length":data["hourly"]["pm2_5"].pop()
    if mutation=="duplicate":data["hourly"]["time"][1]=data["hourly"]["time"][0]
    if mutation=="unsorted":data["hourly"]["time"].reverse()
    if mutation=="naive":clock=NOW.replace(tzinfo=None)
    if mutation=="boolean_time":data["hourly"]["time"][0]=True
    if mutation=="too_many":data["hourly"]["time"]*=2
    with pytest.raises(aq.AirQualityError):aq.normalize(data,clock)

def test_time_current_trend_and_provenance():
    report=aq.render(aq.normalize(payload(),NOW),NOW)
    assert report["current"]["valid_time"]=="2026-10-10T17:00:00+00:00"
    assert len(report["hourly"])==24
    assert report["hourly"][0]["valid_time"]=="2026-10-10T18:00:00+00:00"
    assert report["status"]=="available"
    assert report["source"]["source_type"]=="model_estimate"
    assert report["source"]["model_run_at"] is None
    assert report["source"]["native_temporal_resolution_hours"]==3

def test_future_not_current_missing_and_stale():
    data=aq.normalize(payload(),NOW)
    assert aq.render(data,NOW+timedelta(hours=2))["stale"]
    assert aq.render(data,NOW,error="provider_unavailable")["status"]=="stale"
    assert aq.render(data,NOW-timedelta(days=1))["current"] is None
    for row in data["hourly"]:row.update(pm25=None,aqi=None)
    assert aq.render(data,NOW)["status"]=="missing"
    assert aq.render(None,NOW,error="provider_unavailable")["status"]=="unavailable"

@pytest.mark.asyncio
async def test_singleflight_and_expiry():
    now=[NOW]
    fetch=AsyncMock(return_value=aq.normalize(payload(),NOW))
    service=aq.AirQualityService(fetch,lambda:now[0])
    reports=await asyncio.gather(*(service.get(13,100) for _ in range(8)))
    assert fetch.await_count==1 and all(r["status"]=="available" for r in reports)
    reports[0]["source"]["model"]="mutated"
    assert (await service.get(13,100))["source"]["model"]==aq.SOURCE["model"]
    now[0]+=timedelta(seconds=601)
    await service.get(13,100)
    assert fetch.await_count==2

@pytest.mark.asyncio
async def test_failures_cached_stale_and_location_isolation():
    now=[NOW];fetch=AsyncMock(return_value=aq.normalize(payload(),NOW))
    service=aq.AirQualityService(fetch,lambda:now[0])
    await service.get(13,100)
    now[0]+=timedelta(seconds=601);fetch.side_effect=aq.AirQualityError("secret detail")
    stale=await service.get(13,100)
    assert stale["status"]=="stale" and stale["current"]["pm25"]==10
    missing=await service.get(14,101)
    assert missing["current"] is None and missing["status"]=="unavailable"
    assert missing["error_code"]=="provider_unavailable"
    await service.get(14,101)
    assert fetch.await_count==3

@pytest.mark.asyncio
async def test_cache_bound(monkeypatch):
    monkeypatch.setattr(aq,"MAX_CACHE",2)
    service=aq.AirQualityService(AsyncMock(return_value=aq.normalize(payload(),NOW)),lambda:NOW)
    for latitude in [10,11,12]:await service.get(latitude,100)
    assert len(service.cache)==2 and (10,100) not in service.cache

@pytest.mark.asyncio
async def test_cancellation_releases_lock():
    waiting=asyncio.Event()
    async def fetch(*args):waiting.set();await asyncio.Event().wait()
    service=aq.AirQualityService(fetch,lambda:NOW)
    task=asyncio.create_task(service.get(13,100));await waiting.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert not service.lock.locked() and not service.cache

@pytest.mark.asyncio
@pytest.mark.parametrize("case",["valid","http","oversized","malformed"])
async def test_transport_contract(monkeypatch,case):
    def handler(request):
        assert request.url.host=="air-quality-api.open-meteo.com"
        assert request.url.params["timeformat"]=="unixtime"
        assert request.url.params["domains"]=="cams_global"
        assert request.url.params["hourly"]=="pm2_5,european_aqi"
        if case=="http":return httpx.Response(503,text="private")
        if case=="oversized":return httpx.Response(200,content=b"x"*(aq.MAX_BODY+1))
        if case=="malformed":return httpx.Response(200,json={"error":True})
        return httpx.Response(200,json=payload())
    client=httpx.AsyncClient
    monkeypatch.setattr(aq.httpx,"AsyncClient",lambda **kwargs:client(transport=httpx.MockTransport(handler),**kwargs))
    if case=="valid":assert len((await aq.fetch_air_quality(13,100))["hourly"])==26
    else:
        with pytest.raises(aq.AirQualityError):await aq.fetch_air_quality(13,100)

@pytest.mark.asyncio
async def test_api_active_location_and_no_side_effects(client,db_session):
    from app.main import app
    location=Location(name="Air test",slug="air-test",latitude=13,longitude=100,timezone="Asia/Bangkok")
    db_session.add(location);await db_session.flush()
    fake=aq.AirQualityService(AsyncMock(return_value=aq.normalize(payload(),NOW)),lambda:NOW)
    app.dependency_overrides[aq.get_air_quality_service]=lambda:fake
    response=await client.get(f"/api/v1/air-quality/{location.id}")
    assert response.status_code==200
    body=response.json()
    assert body["location_id"]==location.id and body["timezone"]=="Asia/Bangkok"
    assert body["measurement_available"] is False and body["source"]["aqi_standard"].startswith("European")
    location.is_active=False;await db_session.flush()
    assert (await client.get(f"/api/v1/air-quality/{location.id}")).status_code==404
    assert (await client.get("/api/v1/air-quality/999999")).status_code==404
    assert fake.fetcher.await_count==1
