"""Daily LINE layout and real hourly aggregation, without network access."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.notifications.formatter import format_rain_alert
from app.notifications.rain_risk import RainRiskPeriod

TZ = ZoneInfo("Asia/Bangkok")
DAY = date(2026, 10, 11)
START = datetime(2026, 10, 11, tzinfo=TZ)


def row(hour, amount, probability):
    return SimpleNamespace(valid_time=(START + timedelta(hours=hour)).astimezone(timezone.utc),
                           precipitation=amount, precipitation_probability=probability)


def render(rows, periods=None, daily=None):
    run = SimpleNamespace(location=SimpleNamespace(name="แสนสุข", timezone=TZ.key),
                          retrieved_at=datetime(2026, 10, 10, 23, 1, tzinfo=timezone.utc))
    periods = periods or [RainRiskPeriod(START, START + timedelta(hours=3), 90, 2, 2, 50)]
    return format_rain_alert(run, periods, alert_date=DAY, hourly_rows=rows,
                             daily_rows=daily or [])


def test_entire_window_includes_quiet_gap_and_uses_hourly_probability():
    text = render([row(3, 2, 90), row(1, 1, 80), row(2, 0.2, 10)],
                  daily=[SimpleNamespace(forecast_date=DAY, precipitation_sum=10.8,
                                         precipitation_probability_max=100)])
    assert "🕒 00:00–03:00 น." in text
    assert "โอกาสฝนสูงสุดในช่วง: 90%" in text
    assert "ฝนคาดการณ์รวมในช่วง: 3.2 มม." in text
    assert "ฝนสูงสุดต่อชั่วโมง: 2 มม." in text
    assert "📊 ฝนคาดการณ์รวมทั้งวัน: 10.8 มม." in text
    assert "100%" not in text
    assert text.count("────────────") == 2
    assert "☂️ แนะนำพกร่ม" in text
    assert "ข้อมูลเป็นการพยากรณ์ สภาพอากาศจริงอาจแตกต่างและเปลี่ยนแปลงได้" in text
    assert "อัปเดตพยากรณ์: 11 ตุลาคม 2569 06:01 น." in text
    assert len(text) < 5000


@pytest.mark.parametrize("amount", [None, -1, float("nan"), float("inf"), True])
def test_invalid_rainfall_never_becomes_zero_or_partial_sum(amount):
    text = render([row(1, 1, 80), row(2, amount, 90), row(3, 2, 90)])
    assert "ฝนคาดการณ์รวมในช่วง: ข้อมูลไม่ครบ" in text
    assert "ฝนสูงสุดต่อชั่วโมง: ข้อมูลไม่ครบ" in text
    assert "โอกาสฝนสูงสุดในช่วง: 90%" in text


@pytest.mark.parametrize("probability", [None, -1, 101, float("nan"), True])
def test_invalid_probability_does_not_hide_known_rainfall(probability):
    text = render([row(1, 1, 80), row(2, 0.2, probability), row(3, 2, 90)])
    assert "โอกาสฝนสูงสุดในช่วง: ข้อมูลไม่ครบ" in text
    assert "ฝนคาดการณ์รวมในช่วง: 3.2 มม." in text


def test_gap_is_not_filled_from_selected_period_statistics():
    text = render([row(1, 1, 80), row(3, 2, 90)])
    assert "โอกาสฝนสูงสุดในช่วง: ข้อมูลไม่ครบ" in text
    assert "ฝนคาดการณ์รวมในช่วง: ข้อมูลไม่ครบ" in text


def test_duplicate_identical_hour_is_counted_once_but_conflict_is_missing():
    rows = [row(1, 1, 80), row(2, 0.2, 90), row(3, 2, 90)]
    assert "ฝนคาดการณ์รวมในช่วง: 3.2 มม." in render(rows + [row(2, 0.2, 90)])
    assert "ฝนคาดการณ์รวมในช่วง: ข้อมูลไม่ครบ" in render(rows + [row(2, 4, 90)])


def test_midnight_endpoint_and_naive_utc_are_included_only_in_correct_window():
    period = RainRiskPeriod(START + timedelta(hours=23), START + timedelta(days=1), 80, 1, 1, 1)
    last = row(24, 1.2, 80)
    last.valid_time = last.valid_time.replace(tzinfo=None)
    text = render([row(23, 100, 100), last, row(25, 100, 100)], periods=[period])
    assert "🕒 23:00–00:00 น." in text
    assert "ฝนคาดการณ์รวมในช่วง: 1.2 มม." in text
    assert "โอกาสฝนสูงสุดในช่วง: 80%" in text


def test_windows_are_chronological_and_totals_are_not_rounded_before_sum():
    periods = [RainRiskPeriod(START + timedelta(hours=12), START + timedelta(hours=13), 100, 1, 1, 90),
               RainRiskPeriod(START, START + timedelta(hours=2), 80, 1, 2, 50)]
    text = render([row(1, 0.004, 80), row(2, 0.004, 70), row(13, 2, 100)], periods=periods)
    assert text.index("00:00–02:00") < text.index("12:00–13:00")
    assert "ฝนคาดการณ์รวมในช่วง: 0.01 มม." in text
    assert text.count("────────────") == 3


def test_daily_total_requires_complete_unique_hours():
    rows = [row(hour, 1, 80) for hour in range(1, 25)]
    assert "ฝนคาดการณ์รวมทั้งวัน: 24 มม." in render(rows)
    # Still 24 rows, but one hour is missing and another is duplicated.
    bad = rows[:-1] + [row(23, 1, 80)]
    assert "ฝนคาดการณ์รวมทั้งวัน: ข้อมูลไม่ครบ" in render(bad)


def test_invalid_daily_aggregate_uses_complete_hourly_fallback():
    daily = [SimpleNamespace(forecast_date=DAY, precipitation_sum=float("nan"),
                             precipitation_probability_max=100)]
    rows = [row(hour, 0.1, 80) for hour in range(1, 25)]
    assert "ฝนคาดการณ์รวมทั้งวัน: 2.4 มม." in render(rows, daily=daily)


def test_peak_hour_uses_amount_not_highest_probability():
    text = render([row(3, 1, 100), row(2, 4.9, 80), row(1, 0.1, 90)])
    assert "ชั่วโมงที่คาดว่าฝนมากที่สุด: 01:00–02:00 น." in text


def test_tied_peak_hours_are_all_shown_in_time_order():
    text = render([row(3, 4.9, 80), row(1, 4.9, 90), row(2, 1, 100)])
    assert "ชั่วโมงที่คาดว่าฝนมากที่สุด: 00:00–01:00, 02:00–03:00 น." in text


def test_display_rounding_does_not_create_false_peak_ties():
    text = render([row(1, 1.234, 80), row(2, 1.233, 90), row(3, 0, 90)])
    assert "ฝนสูงสุดต่อชั่วโมง: 1.23 มม." in text
    assert "ชั่วโมงที่คาดว่าฝนมากที่สุด: 00:00–01:00 น." in text


@pytest.mark.parametrize("rows", [
    [row(1, 1, 80), row(3, 2, 90)],
    [row(1, 1, 80), row(2, None, 90), row(3, 2, 90)],
    [row(1, 1, 80), row(2, 1, 90), row(2, 2, 90), row(3, 2, 90)],
])
def test_incomplete_rainfall_has_no_guessed_peak_hour(rows):
    assert "ชั่วโมงที่คาดว่าฝนมากที่สุด: ข้อมูลไม่ครบ" in render(rows)


def test_all_zero_rain_has_no_arbitrary_peak_hour():
    text = render([row(1, 0, 80), row(2, 0, 90), row(3, 0, 90)])
    assert "ชั่วโมงที่คาดว่าฝนมากที่สุด: ไม่มีฝนคาดการณ์ในช่วงนี้" in text


def test_peak_hour_at_midnight_uses_preceding_interval_and_naive_utc():
    period = RainRiskPeriod(START + timedelta(hours=23), START + timedelta(days=1), 80, 1, 1, 1)
    last = row(24, 1.2, 80)
    last.valid_time = last.valid_time.replace(tzinfo=None)
    assert "ชั่วโมงที่คาดว่าฝนมากที่สุด: 23:00–00:00 น." in render([last], periods=[period])
