"""Delivery provenance regressions using only SQLite and mocked LINE."""
import copy
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select, update

from app.models.forecast import DailyForecast, ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.notifications.formatter import format_rain_alert
from app.notifications.line_client import LineApiError
from app.notifications.rain_alerts import send_rain_alert
from app.notifications.rain_risk import RainRiskPeriod

UTC = timezone.utc
TZ = ZoneInfo("Asia/Bangkok")


async def make_run(db, probability=80, *, model_time=None, timezone_name="Asia/Bangkok"):
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    location = Location(name="Evidence Area", slug="evidence-area", latitude=13,
                        longitude=100, timezone=timezone_name, provider="open_meteo")
    db.add(location)
    await db.flush()
    run = ForecastRun(location_id=location.id, provider="open_meteo",
                      retrieved_at=datetime.now(UTC), model_run_time=model_time)
    db.add(run)
    await db.flush()
    for hour in range(24):
        db.add(HourlyForecast(
            forecast_run_id=run.id,
            valid_time=(datetime.combine(today, time(hour), tz) + timedelta(hours=1)).astimezone(UTC),
            precipitation_probability=probability if hour == 15 else 10,
            precipitation=0.5 if hour == 15 else 0.01,
        ))
    db.add(DailyForecast(forecast_run_id=run.id, forecast_date=today,
                        precipitation_probability_max=95, precipitation_sum=7.25))
    await db.flush()
    return run, today


def replay(evidence):
    """Reformat from persisted inputs without reading any live source rows."""
    source = evidence["source"]
    run = ForecastRun(retrieved_at=datetime.fromisoformat(source["retrieved_at"]))
    run.location = Location(name="Evidence Area", timezone=evidence["timezone"])
    periods = [RainRiskPeriod(**{**row, "start": datetime.fromisoformat(row["start"]),
                                "end": datetime.fromisoformat(row["end"])})
               for row in evidence["selected_periods"]]
    hours = [HourlyForecast(valid_time=datetime.fromisoformat(row["end"]),
                            precipitation_probability=row["precipitation_probability"],
                            precipitation=row["precipitation_mm"])
             for row in evidence["hourly_intervals"]]
    day = evidence["daily_aggregate"]
    daily = [] if day is None else [DailyForecast(
        forecast_date=datetime.fromisoformat(day["forecast_date"]).date(),
        precipitation_probability_max=day["precipitation_probability_max"],
        precipitation_sum=day["precipitation_sum_mm"],
    )]
    return format_rain_alert(run, periods,
                             alert_date=datetime.fromisoformat(evidence["alert_local_date"]).date(),
                             hourly_rows=hours, daily_rows=daily,
                             daily_peak=evidence["mode"] == "daily_peak")


@pytest.mark.asyncio
@pytest.mark.parametrize("probability,mode", [
    (80, "strong_rain"), (35, "daily_peak"), (20, "below_threshold_daily_summary"),
])
async def test_exact_formatted_run_survives_source_and_latest_changes(db_session, probability, mode):
    model_time = datetime(2026, 10, 1, tzinfo=UTC) if probability == 80 else None
    run, today = await make_run(db_session, probability, model_time=model_time)
    # A newer source already exists. Direct send must still evidence its supplied run.
    newer = ForecastRun(location_id=run.location_id, provider="other",
                        retrieved_at=run.retrieved_at + timedelta(seconds=1))
    db_session.add(newer)
    await db_session.flush()
    client = AsyncMock()
    assert await send_rain_alert(db_session, run, "U_EVIDENCE", client)
    delivery = await db_session.scalar(select(NotificationDelivery))
    original = copy.deepcopy(delivery.rain_evidence)
    assert delivery.forecast_run_id == run.id != newer.id
    assert original["source"] == {
        "forecast_run_id": run.id, "provider": "open_meteo",
        "retrieved_at": run.retrieved_at.isoformat(),
        "model_run_time": model_time.isoformat() if model_time else None,
    }
    assert original["mode"] == mode
    assert original["alert_local_date"] == today.isoformat()
    assert original["timezone"] == "Asia/Bangkok"
    assert original["schema_version"] == 1
    assert original["template_version"] and original["selection_version"]
    assert original["message_text"] == client.push_text.await_args.args[1] == replay(original)
    assert len(original["hourly_intervals"]) == 24
    first = datetime.fromisoformat(original["hourly_intervals"][0]["start"]).astimezone(TZ)
    last = datetime.fromisoformat(original["hourly_intervals"][-1]["end"]).astimezone(TZ)
    assert first == datetime.combine(today, time(0), TZ)
    assert last == datetime.combine(today + timedelta(days=1), time(0), TZ)
    assert original["daily_aggregate"]["precipitation_probability_max"] == 95
    if mode == "below_threshold_daily_summary":
        assert original["selected_periods"] == []
    else:
        period = original["selected_periods"][0]
        assert period["max_probability"] == probability != 95
        assert period["max_rainfall_mm"] == 0.5
        assert datetime.fromisoformat(period["start"]).astimezone(TZ).hour == 15
        assert datetime.fromisoformat(period["end"]).astimezone(TZ).hour == 16
    assert "U_EVIDENCE" not in str(original)
    assert "latitude" not in str(original) and "longitude" not in str(original)

    await db_session.execute(update(ForecastRun).where(ForecastRun.id == run.id)
                             .values(provider="changed", model_run_time=datetime.now(UTC)))
    await db_session.execute(update(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
                             .values(precipitation_probability=99, precipitation=100))
    await db_session.execute(update(DailyForecast).where(DailyForecast.forecast_run_id == run.id)
                             .values(precipitation_sum=1000))
    await db_session.execute(update(ForecastRun).where(ForecastRun.id == newer.id)
                             .values(retrieved_at=datetime.now(UTC) + timedelta(hours=1)))
    # Recipient/location/day dedupe holds even for a different run.
    assert not await send_rain_alert(db_session, run, "U_EVIDENCE", client)
    await db_session.refresh(delivery)
    assert delivery.rain_evidence == original
    assert replay(delivery.rain_evidence) == client.push_text.await_args.args[1]
    client.push_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_summary_without_daily_aggregate_replays_full_hourly_total(db_session):
    run, _ = await make_run(db_session, 20, timezone_name="UTC")
    await db_session.execute(delete(DailyForecast).where(DailyForecast.forecast_run_id == run.id))
    client = AsyncMock()
    assert await send_rain_alert(db_session, run, "U_EVIDENCE", client)
    delivery = await db_session.scalar(select(NotificationDelivery))
    assert delivery.rain_evidence["daily_aggregate"] is None
    assert delivery.rain_evidence["timezone"] == "UTC"
    assert delivery.rain_evidence["source"]["model_run_time"] is None
    assert replay(delivery.rain_evidence) == client.push_text.await_args.args[1]


@pytest.mark.asyncio
async def test_only_selected_top_periods_are_frozen_in_score_order(db_session):
    run, today = await make_run(db_session, 20)
    for hour, probability in [(2, 75), (9, 80), (15, 95)]:
        end = (datetime.combine(today, time(hour), TZ) + timedelta(hours=1)).astimezone(UTC)
        await db_session.execute(update(HourlyForecast)
                                 .where(HourlyForecast.forecast_run_id == run.id,
                                        HourlyForecast.valid_time == end)
                                 .values(precipitation_probability=probability, precipitation=0.5))
    client = AsyncMock()
    assert await send_rain_alert(db_session, run, "U_EVIDENCE", client)
    delivery = await db_session.scalar(select(NotificationDelivery))
    evidence = delivery.rain_evidence
    assert [p["max_probability"] for p in evidence["selected_periods"]] == [95, 80]
    assert [datetime.fromisoformat(p["start"]).astimezone(TZ).hour
            for p in evidence["selected_periods"]] == [15, 9]
    assert replay(evidence) == client.push_text.await_args.args[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("skip", ["stale", "no_data", "incomplete"])
async def test_skipped_paths_create_no_history(db_session, skip):
    run, _ = await make_run(db_session, 20)
    if skip == "stale":
        run.retrieved_at -= timedelta(days=2)
    elif skip == "no_data":
        await db_session.execute(delete(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id))
    else:
        await db_session.execute(update(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
                                 .values(precipitation_probability=None))
    client = AsyncMock()
    assert not await send_rain_alert(db_session, run, "U_EVIDENCE", client)
    assert await db_session.scalar(select(NotificationDelivery)) is None
    client.push_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_push_then_retry_evidences_only_successful_message(db_session):
    run, _ = await make_run(db_session, 20)
    client = AsyncMock()
    client.push_text.side_effect = LineApiError("mock failure")
    with pytest.raises(LineApiError):
        await send_rain_alert(db_session, run, "U_EVIDENCE", client)
    assert await db_session.scalar(select(NotificationDelivery)) is None
    await db_session.execute(update(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
                             .values(precipitation_probability=80))
    client.push_text.side_effect = None
    assert await send_rain_alert(db_session, run, "U_EVIDENCE", client)
    rows = list((await db_session.scalars(select(NotificationDelivery))).all())
    assert len(rows) == 1
    assert rows[0].rain_evidence["mode"] == "strong_rain"
    assert rows[0].rain_evidence["message_text"] == client.push_text.await_args.args[1]


@pytest.mark.asyncio
async def test_legacy_orm_record_keeps_unknown_provenance(db_session):
    run, _ = await make_run(db_session)
    delivery = NotificationDelivery(location_id=run.location_id, channel="line",
                                    recipient_id="U_LEGACY", dedupe_key="legacy")
    db_session.add(delivery)
    await db_session.flush()
    await db_session.refresh(delivery)
    assert delivery.forecast_run_id is None and delivery.rain_evidence is None
