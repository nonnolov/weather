"""Synthetic snapshots and mock sender only: no external APIs or LINE."""
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.models.forecast import ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.notifications.flood_enrichment import (
    FLOOD_WATCH_TEXT, enrich_rain_message, flood_enrichment, read_flood_snapshot,
)
from app.notifications.intraday_delivery import deliver_intraday_update
from app.notifications.intraday_formatter import format_intraday_alert, freeze_intraday_evidence
from tests.test_intraday_baseline import NOW, H, candidate, delivery, sessions
from tests.test_intraday_delivery import decision_for
from tests.test_rainfall_flood_assessment import make_run, NOW as RAIN_NOW
from tests.test_rainfall_flood_screening import location


@pytest.mark.parametrize("kind", ["positive", "below", "missing", "stale", "unsupported"])
def test_sentence_only_for_valid_positive_result(kind):
    run = make_run(([40] if kind == "positive" else [0]) + [0] * 23)
    loc = location()
    if kind == "missing":
        run.hourly_forecasts[5].precipitation = None
    if kind == "stale":
        run.retrieved_at = RAIN_NOW - 7 * H
    if kind == "unsupported":
        loc.country_code = None
    evidence = flood_enrichment(run, run.hourly_forecasts, loc, now=RAIN_NOW)
    result = enrich_rain_message("base", evidence, source_id=17, location_id=8)
    assert (FLOOD_WATCH_TEXT in result) is (kind == "positive")
    if kind != "positive":
        assert result == "base"


def test_wrong_source_and_location_never_add_sentence():
    run = make_run([40] + [0]*23)
    evidence = flood_enrichment(run, run.hourly_forecasts, location(), now=RAIN_NOW)
    assert enrich_rain_message("base", evidence, source_id=18, location_id=8) == "base"
    assert enrich_rain_message("base", evidence, source_id=17, location_id=9) == "base"


def test_intraday_formatter_freezes_rain_only_message():
    new = candidate()
    decision = decision_for(new)
    rendered = format_intraday_alert(new, decision, now=NOW, location_name="test")
    frozen = freeze_intraday_evidence(new, decision, rendered, now=NOW, baseline_delivery_id=1)
    assert FLOOD_WATCH_TEXT not in rendered.message
    assert frozen["message_text"] == rendered.message
    assert frozen["comparison"]["event_id"] == decision.event_id
    assert "flood_screening" not in frozen
    assert "latitude" not in str(frozen) and "recipient_id" not in str(frozen)


@pytest.mark.asyncio
@pytest.mark.parametrize("rain", [0,40])
async def test_delivery_preview_keeps_rain_only_even_for_heavy_bangkok_rain(
        sessions, monkeypatch, rain):
    new = replace(candidate(), hours=tuple(replace(h, rainfall_mm=rain if i==0 else 0)
                                           for i,h in enumerate(candidate().hours)))
    async with sessions() as db:
        loc = await db.get(Location, 101)
        loc.latitude, loc.longitude, loc.country_code, loc.province = 13.75,100.5,"TH","Bangkok"
        db.add(ForecastRun(id=12, location_id=101, provider="open_meteo",
                          retrieved_at=new.retrieved_at))
        db.add(delivery())
        await db.flush()
        db.add_all(HourlyForecast(forecast_run_id=12, valid_time=h.end,
                                 precipitation_probability=float(h.probability),
                                 precipitation=float(h.rainfall_mm)) for h in new.hours)
        # Fill tomorrow's hours too: current-day candidate alone is not a 24h horizon.
        db.add_all(HourlyForecast(forecast_run_id=12, valid_time=NOW+(i+1)*H,
                                 precipitation_probability=10, precipitation=0)
                   for i in range(6,24))
        db.add(ForecastRun(id=13, location_id=101, provider="other",
                          retrieved_at=NOW))
        await db.commit()

    @asynccontextmanager
    async def synthetic_scope(*args, **kwargs):
        kwargs["clock"]()
        async with sessions() as db:
            async with db.begin():
                yield SimpleNamespace(session=db, decision=decision_for(new))
    # SQLite exercises the real DB/format/preview path. PostgreSQL locking itself
    # remains covered by the existing opt-in dedicated PostgreSQL suite.
    monkeypatch.setattr("app.notifications.intraday_delivery.locked_intraday_evaluation",
                        synthetic_scope)
    # Candidate must contain every persisted interval starting on this local day.
    new = replace(new, hours=new.hours + tuple(
        replace(new.hours[-1], start=NOW+i*H, end=NOW+(i+1)*H,
                probability=10, rainfall_mm=0) for i in range(6,14)))
    client = AsyncMock()
    result = await deliver_intraday_update(sessions, new, clock=lambda:NOW,
                                          client=client, dry_run=True)
    assert result.status == "preview", result.decision.reasons
    assert FLOOD_WATCH_TEXT not in result.message
    client.push_text.assert_not_awaited()
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
        snap = await read_flood_snapshot(db, 12, 101)
        evidence = flood_enrichment(*snap, now=NOW)
        assert evidence["forecast_run_id"] == 12
        assert evidence["risk_detected"] is (rain==40)
        assert await read_flood_snapshot(db, 12, 102) is None


@pytest.mark.asyncio
async def test_suppressed_decision_never_reads_flood_or_sends(sessions, monkeypatch):
    from app.notifications.intraday_comparison import Decision
    @asynccontextmanager
    async def suppressed(*args, **kwargs):
        yield SimpleNamespace(session=None, decision=Decision("suppress", ("cooldown",)))
    monkeypatch.setattr("app.notifications.intraday_delivery.locked_intraday_evaluation", suppressed)
    forbidden = AsyncMock(side_effect=AssertionError("Suppression must not enrich"))
    monkeypatch.setattr("app.notifications.flood_enrichment.read_flood_snapshot", forbidden)
    client = AsyncMock()
    result = await deliver_intraday_update(sessions, candidate(), clock=lambda:NOW,
                                          client=client, dry_run=True)
    assert result.status == "suppress" and result.message is None
    forbidden.assert_not_awaited()
    client.push_text.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("rain", [0,40])
async def test_daily_alert_is_rain_only_frozen_and_deduplicated(db_session, monkeypatch, rain):
    import app.notifications.rain_alerts as daily_module
    from app.models.forecast import DailyForecast
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz or timezone.utc)
    monkeypatch.setattr(daily_module, "datetime", Clock)
    loc = Location(name="Test", slug="flood-daily", latitude=13.75, longitude=100.5,
                   country_code="TH", province="Bangkok", timezone="Asia/Bangkok")
    db_session.add(loc)
    await db_session.flush()
    run = ForecastRun(location_id=loc.id, provider="open_meteo", retrieved_at=NOW)
    db_session.add(run)
    await db_session.flush()
    db_session.add_all(HourlyForecast(
        forecast_run_id=run.id, valid_time=NOW+(i+1)*H,
        precipitation=rain if i==0 else 0, precipitation_probability=90 if i==0 else 10,
    ) for i in range(24))
    db_session.add(DailyForecast(forecast_run_id=run.id, forecast_date=NOW.date(),
                                precipitation_probability_max=90, precipitation_sum=rain))
    await db_session.flush()
    client = AsyncMock()
    assert await daily_module.send_rain_alert(db_session, run, "U_SYNTHETIC", client)
    saved = await db_session.scalar(select(NotificationDelivery))
    assert saved.rain_evidence["message_text"] == client.push_text.await_args.args[1]
    assert FLOOD_WATCH_TEXT not in saved.rain_evidence["message_text"]
    assert "flood_screening" not in saved.rain_evidence
    assert "latitude" not in str(saved.rain_evidence)
    assert not await daily_module.send_rain_alert(db_session, run, "U_SYNTHETIC", client)
    client.push_text.assert_awaited_once()


from tests.test_intraday_delivery import pg, source_sessions
from tests.test_rain_locking_postgres import pg_sessions


@pg
@pytest.mark.asyncio
async def test_real_postgres_heavy_rain_only_preview_mock_send_and_replay(source_sessions):
    from sqlalchemy import update
    new = candidate()
    new = replace(new, hours=tuple(replace(h, rainfall_mm=40 if i==0 else 0)
                                   for i,h in enumerate(new.hours)))
    async with source_sessions() as db:
        loc = await db.get(Location, 101)
        loc.latitude, loc.longitude, loc.country_code, loc.province = 13.75,100.5,"TH","Bangkok"
        await db.execute(update(HourlyForecast).where(
            HourlyForecast.forecast_run_id==12, HourlyForecast.valid_time==NOW+H,
        ).values(precipitation=40))
        db.add_all(HourlyForecast(forecast_run_id=12, valid_time=NOW+(i+1)*H,
                                 precipitation=0, precipitation_probability=10)
                   for i in range(6,24))
        await db.commit()
    new = replace(new, hours=new.hours + tuple(
        replace(new.hours[-1], start=NOW+i*H, end=NOW+(i+1)*H,
                probability=10, rainfall_mm=0) for i in range(6,14)))
    client = AsyncMock()
    preview = await deliver_intraday_update(source_sessions, new, clock=lambda:NOW,
                                           client=client, dry_run=True)
    assert preview.status == "preview" and FLOOD_WATCH_TEXT not in preview.message
    client.push_text.assert_not_awaited()
    sent = await deliver_intraday_update(source_sessions, new, clock=lambda:NOW,
                                        client=client, dry_run=False)
    assert sent.status == "sent" and sent.message == preview.message
    async with source_sessions() as db:
        saved = await db.get(NotificationDelivery, sent.delivery_id)
        assert "flood_screening" not in saved.rain_evidence
        assert saved.rain_evidence["message_text"] == sent.message
    replay = await deliver_intraday_update(source_sessions, new, clock=lambda:NOW,
                                          client=client, dry_run=False)
    assert replay.status == "suppress"
    client.push_text.assert_awaited_once()
