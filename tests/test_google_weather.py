from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from app.providers.google_weather import GoogleWeatherProvider
from app.providers.registry import get_provider
from app.core.config import settings
from app.ingestion.fetch_control import ForecastControlError
from app.ingestion.service import ingest_forecast_for_location, IngestionError


def hour(start, **extra):
    return {"interval":{"startTime":start.isoformat(),"endTime":(start+timedelta(hours=1)).isoformat()},
        "precipitation":{"probability":{"percent":35},"qpf":{"quantity":4.9,"unit":"MILLIMETERS"}},
        "temperature":{"degrees":29,"unit":"CELSIUS"}, "visibility":{"distance":8,"unit":"KILOMETERS"},
        **extra}


def raw(rows):
    return {"forecastHours":rows,"timeZone":{"id":"Asia/Bangkok"}}


def test_google_registered_but_not_production_eligible():
    assert get_provider("google_weather").name == "google_weather"


@pytest.mark.asyncio
async def test_google_live_default_is_blocked(monkeypatch):
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_CONTRACT_VERIFIED",False)
    with pytest.raises(ForecastControlError): await GoogleWeatherProvider().fetch_forecast(13,100)


@pytest.mark.asyncio
async def test_google_ingestion_is_blocked_before_network():
    with pytest.raises(IngestionError,match="transient-only"):
        await ingest_forecast_for_location(AsyncMock(),SimpleNamespace(provider="google_weather"),7)


@pytest.mark.asyncio
async def test_google_modeled_history_not_measured_observations():
    with pytest.raises(ForecastControlError): await GoogleWeatherProvider().fetch_observations(13,100,None,None)


def test_explicit_hour_end_units_and_missing_weather_code():
    start=datetime(2026,10,11,11,tzinfo=timezone.utc)
    result=GoogleWeatherProvider.normalize(raw([hour(start)]))
    h=result.hourly[0]
    assert h.valid_time==start+timedelta(hours=1)
    assert h.precipitation==4.9 and h.precipitation_probability==35
    assert h.visibility==8000 and h.temperature_2m==29
    assert h.weather_code is None
    assert result.daily[0].precipitation_sum is None
    assert result.metadata["transient_only"] is True


def test_complete_local_day_sum_and_peak():
    start=datetime(2026,10,10,17,tzinfo=timezone.utc)
    result=GoogleWeatherProvider.normalize(raw([hour(start+timedelta(hours=i)) for i in range(24)]))
    assert result.daily[0].forecast_date.isoformat()=="2026-10-11"
    assert result.daily[0].precipitation_sum==pytest.approx(117.6)
    assert result.daily[0].precipitation_probability_max==35


@pytest.mark.parametrize("rain", [{},{"probability":{"percent":101},"qpf":{"quantity":-1,"unit":"MILLIMETERS"}},
    {"probability":{"percent":None},"qpf":{"quantity":1,"unit":"INCHES"}}])
def test_unknown_invalid_and_wrong_unit_rain_remains_missing(rain):
    result=GoogleWeatherProvider.normalize(raw([hour(datetime(2026,10,11,tzinfo=timezone.utc),precipitation=rain)]))
    assert result.hourly[0].precipitation is None and result.hourly[0].precipitation_probability is None


@pytest.mark.parametrize("offset", [0,2])
def test_duplicate_or_gap_rejected(offset):
    start=datetime(2026,10,11,tzinfo=timezone.utc)
    with pytest.raises(ForecastControlError): GoogleWeatherProvider.normalize(raw([hour(start),hour(start+timedelta(hours=offset))]))


@pytest.mark.asyncio
async def test_google_pagination_and_key_header(monkeypatch):
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_API_KEY","test-only-key")
    start=datetime(2026,10,11,tzinfo=timezone.utc); calls=[]
    def handler(request):
        calls.append(request)
        page=len(calls)-1
        assert "key" not in request.url.params
        assert request.headers["x-goog-api-key"]=="test-only-key"
        body=raw([hour(start+timedelta(hours=page*24+i)) for i in range(24)])
        if page==0:body["nextPageToken"]="page-2"
        else:assert request.url.params["pageToken"]=="page-2"
        return httpx.Response(200,json=body)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        output=await GoogleWeatherProvider()._fetch_pages(client,13,100,48)
    assert len(calls)==2 and len(output["forecastHours"])==48


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body", [(503,{}),(200,raw([])),(200,{"forecastHours":[{}],"timeZone":{"id":"UTC"},"nextPageToken":"same"})])
async def test_failed_or_truncated_google_fetch_not_accepted(status,body,monkeypatch):
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_API_KEY","test-only-key")
    def handler(request):return httpx.Response(status,json=body)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ForecastControlError):await GoogleWeatherProvider()._fetch_pages(client,13,100,24)
