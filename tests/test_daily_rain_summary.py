from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, update

from app.models.forecast import DailyForecast, ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.notifications.formatter import format_rain_alert
from app.notifications.line_client import LineApiError
from app.notifications.rain_alerts import send_rain_alert

TZ = ZoneInfo("Asia/Bangkok")


async def setup_run(db, probability=20, rainfall=0.02, stale=False, empty=False):
    today = datetime.now(TZ).date()
    loc = Location(name="Test Area", slug="daily-summary", latitude=13,
                   longitude=100, timezone="Asia/Bangkok", provider="open_meteo")
    db.add(loc)
    await db.flush()
    run = ForecastRun(location_id=loc.id, provider="open_meteo", forecast_days=7,
                      retrieved_at=datetime.now(timezone.utc) - timedelta(days=int(stale)))
    db.add(run)
    await db.flush()
    for hour in range(24):
        db.add(HourlyForecast(
            forecast_run_id=run.id,
            valid_time=(datetime.combine(today, time(hour), TZ)).astimezone(timezone.utc),
            precipitation_probability=None if empty else probability,
            precipitation=None if empty else rainfall,
        ))
    db.add(DailyForecast(forecast_run_id=run.id, forecast_date=today,
                        precipitation_probability_max=None if empty else probability,
                        precipitation_sum=None if empty else rainfall * 24))
    await db.flush()
    return run


@pytest.mark.asyncio
async def test_below_threshold_summary_sent_and_deduplicated(db_session):
    run = await setup_run(db_session)
    client = AsyncMock()
    assert await send_rain_alert(db_session, run, "U_TEST", client)
    assert not await send_rain_alert(db_session, run, "U_TEST", client)
    client.push_text.assert_awaited_once()
    text = client.push_text.await_args.args[1]
    assert "🌤️ สรุปฝนวันนี้" in text
    assert "พยากรณ์ฝนยังไม่ถึงเกณฑ์" in text
    assert "แจ้งเตือน" not in text
    assert "โอกาสฝนสูงสุด: 20%" in text
    assert "ปริมาณฝนคาดการณ์รวมวันนี้: 0.48 มม." in text
    assert "ช่วงที่ควรระวัง" not in text
    assert "อัปเดตพยากรณ์:" in text
    assert "https://weather-iota-five-83.vercel.app" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("probability,rainfall", [(80, 0.5), (35, 1)])
async def test_rain_and_existing_daily_peak_keep_warning_template(db_session, probability, rainfall):
    run = await setup_run(db_session, probability, rainfall)
    client = AsyncMock()
    assert await send_rain_alert(db_session, run, "U_TEST", client)
    text = client.push_text.await_args.args[1]
    assert "🌧️ แจ้งเตือนฝนวันนี้" in text
    assert "มีโอกาสฝนถึงเกณฑ์แจ้งเตือน" in text
    assert "ช่วงที่ควรระวัง:" in text
    assert "แนะนำพกร่มและตรวจพยากรณ์ก่อนออกเดินทาง" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [{"stale": True}, {"empty": True}])
async def test_stale_or_missing_rain_data_never_sent_as_clear_day(db_session, options):
    run = await setup_run(db_session, **options)
    client = AsyncMock()
    assert not await send_rain_alert(db_session, run, "U_TEST", client)
    client.push_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_push_does_not_record_success(db_session):
    run = await setup_run(db_session)
    client = AsyncMock()
    client.push_text.side_effect = LineApiError("failed")
    with pytest.raises(LineApiError):
        await send_rain_alert(db_session, run, "U_TEST", client)
    assert await db_session.scalar(select(func.count()).select_from(NotificationDelivery)) == 0
    client.push_text.side_effect = None
    assert await send_rain_alert(db_session, run, "U_TEST", client)


def test_format_summary_uses_local_day_omits_partial_total_and_actual_update():
    today = datetime(2026, 10, 7).date()
    run = ForecastRun(retrieved_at=datetime(2026, 10, 6, 23, 12, tzinfo=timezone.utc))
    run.location = Location(name="Test Area", timezone="Asia/Bangkok")
    hours = [
        HourlyForecast(valid_time=datetime(2026, 10, 6, 17, tzinfo=timezone.utc),
                       precipitation_probability=20, precipitation=0.1),
        HourlyForecast(valid_time=datetime(2026, 10, 7, 17, tzinfo=timezone.utc),
                       precipitation_probability=99, precipitation=10),
    ]
    text = format_rain_alert(run, [], alert_date=today, hourly_rows=hours)
    assert "📅 7 ตุลาคม 2569" in text
    assert "โอกาสฝนสูงสุด: 20%" in text
    assert "99%" not in text
    assert "ปริมาณฝนคาดการณ์รวมวันนี้" not in text
    assert "อัปเดตพยากรณ์: 7 ตุลาคม 2569 06:12 น." in text


def test_format_omits_missing_values_without_inventing_zero():
    run = ForecastRun(retrieved_at=datetime(2026, 10, 7, tzinfo=timezone.utc))
    run.location = Location(name="Test Area", timezone="Asia/Bangkok")
    text = format_rain_alert(run, [], alert_date=datetime(2026, 10, 7).date(), hourly_rows=[])
    assert "โอกาสฝนสูงสุด" not in text
    assert "ปริมาณฝนคาดการณ์รวมวันนี้" not in text


@pytest.mark.asyncio
async def test_incomplete_probability_is_not_sent_as_below_threshold(db_session):
    run = await setup_run(db_session)
    await db_session.execute(
        update(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
        .values(precipitation_probability=None)
    )
    client = AsyncMock()
    assert not await send_rain_alert(db_session, run, "U_TEST", client)
    client.push_text.assert_not_awaited()
