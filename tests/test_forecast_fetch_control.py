from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text
from app.core.database import Base
from app.core.config import settings
from app.models.forecast_fetch import ProviderRequestBudget
from app.ingestion.fetch_control import acquisition_scope, fetch_shared_forecast, reserve_requests, ForecastControlError
from app.providers.base import ProviderForecastResult, NormalizedHourlyForecast

NOW = datetime(2026, 10, 11, 11, tzinfo=timezone.utc)


def location(lat=13.264196, lon=100.926522, **overrides):
    return SimpleNamespace(**{**dict(latitude=lat, longitude=lon, slug="gps-location-test", provider="open_meteo",
        timezone="Asia/Bangkok", country_code="TH", province="Chonburi", district="Mueang", subdistrict="Saensuk"), **overrides})


def provider():
    result = ProviderForecastResult(provider="open_meteo", retrieved_at=NOW, model_run_time=None,
        hourly=[NormalizedHourlyForecast(valid_time=NOW + timedelta(hours=1), precipitation=4.9, precipitation_probability=92)],
        metadata={"timezone": "Asia/Bangkok"})
    return SimpleNamespace(fetch_forecast=AsyncMock(return_value=result))


@pytest_asyncio.fixture
async def sessions(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "control.db"))
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.parametrize("lat,lon", [(13.264470,100.925995),(13.264299,100.926350),(13.264413,100.926813)])
def test_current_four_gps_points_share_query_cell(lat, lon):
    assert acquisition_scope(location(lat, lon), 7, NOW) == acquisition_scope(location(), 7, NOW)


@pytest.mark.parametrize("overrides", [dict(provider="google_weather"),dict(timezone="UTC"),dict(province="other"),dict(subdistrict="other"),dict(slug="seed")])
def test_scope_does_not_mix_providers_admin_timezone_or_seed(overrides):
    assert acquisition_scope(location(**overrides), 7, NOW)[0] != acquisition_scope(location(), 7, NOW)[0]


def test_scope_separates_cells_days_and_local_midnight():
    key = acquisition_scope(location(), 7, NOW)[0]
    assert acquisition_scope(location(lon=100.93), 7, NOW)[0] != key
    assert acquisition_scope(location(), 1, NOW)[0] != key
    assert acquisition_scope(location(), 7, NOW+timedelta(days=1))[0] != key


@pytest.mark.parametrize("value", [float("nan"),float("inf"),91])
def test_invalid_coordinates_fail(value):
    with pytest.raises(ForecastControlError): acquisition_scope(location(lat=value), 7, NOW)


@pytest.mark.asyncio
async def test_reuse_preserves_retrieval_time_and_values(sessions):
    p = provider()
    first = await fetch_shared_forecast(location(),7,p,sessions,clock=lambda:NOW)
    second = await fetch_shared_forecast(location(13.264470,100.925995),7,p,sessions,clock=lambda:NOW+timedelta(minutes=59))
    assert p.fetch_forecast.await_count == 1
    assert second.retrieved_at == first.retrieved_at == NOW
    assert second.hourly == first.hourly
    assert second.metadata["acquisition_cache_hit"] is True
    async with sessions() as db:
        assert (await db.get(ProviderRequestBudget,("open_meteo","m:2026-10"))).reserved == 1


@pytest.mark.asyncio
async def test_expiry_calls_provider_again(sessions):
    p = provider()
    await fetch_shared_forecast(location(),7,p,sessions,clock=lambda:NOW)
    await fetch_shared_forecast(location(),7,p,sessions,clock=lambda:NOW+timedelta(hours=1))
    assert p.fetch_forecast.await_count == 2


@pytest.mark.asyncio
async def test_failure_backoff_and_reservation_survive(sessions):
    p=provider(); p.fetch_forecast.side_effect=RuntimeError("secret URL")
    for minute in [0,1]:
        with pytest.raises(ForecastControlError) as error:
            await fetch_shared_forecast(location(),7,p,sessions,clock=lambda:NOW+timedelta(minutes=minute))
        assert "secret" not in str(error.value)
    assert p.fetch_forecast.await_count == 1
    async with sessions() as db:
        assert (await db.get(ProviderRequestBudget,("open_meteo","m:2026-10"))).reserved == 1


@pytest.mark.asyncio
async def test_google_never_enters_durable_cache(sessions):
    p=provider()
    with pytest.raises(ForecastControlError): await fetch_shared_forecast(location(provider="google_weather"),7,p,sessions,clock=lambda:NOW)
    p.fetch_forecast.assert_not_awaited()


@pytest.mark.asyncio
async def test_monthly_budget_is_hard_limit(sessions,monkeypatch):
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_MONTHLY_LIMIT",3)
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_DAILY_LIMIT",10)
    await reserve_requests(sessions,"google_weather",3,now=NOW)
    with pytest.raises(ForecastControlError): await reserve_requests(sessions,"google_weather",1,now=NOW)
    async with sessions() as db:
        assert (await db.get(ProviderRequestBudget,("google_weather","m:2026-10"))).reserved == 3


@pytest.mark.asyncio
async def test_daily_limit(sessions,monkeypatch):
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_DAILY_LIMIT",2)
    await reserve_requests(sessions,"google_weather",2,now=NOW)
    with pytest.raises(ForecastControlError): await reserve_requests(sessions,"google_weather",1,now=NOW)


@pytest.mark.asyncio
async def test_month_boundary_does_not_reset_early(sessions,monkeypatch):
    monkeypatch.setattr(settings,"GOOGLE_WEATHER_MONTHLY_LIMIT",2)
    t=datetime(2026,10,31,23,59,tzinfo=timezone.utc)
    await reserve_requests(sessions,"google_weather",2,now=t)
    with pytest.raises(ForecastControlError): await reserve_requests(sessions,"google_weather",1,now=t+timedelta(minutes=2))
