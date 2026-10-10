from datetime import datetime, timezone

from app.models.forecast import HourlyForecast
from app.notifications.rain_risk import find_daily_peak_period, find_rain_risk_periods


def _hour(index: int, probability: float, rainfall: float) -> HourlyForecast:
    return HourlyForecast(
        valid_time=datetime(2026, 10, 4, index, tzinfo=timezone.utc),
        precipitation_probability=probability,
        precipitation=rainfall,
    )


def test_rain_risk_groups_one_hour_gap_and_ranks_top_two() -> None:
    rows = [
        _hour(8, 80, 2),
        _hour(11, 90, 12),
        _hour(14, 75, 1),
        _hour(15, 80, 3),
        _hour(16, 82, 2),
    ]

    periods = find_rain_risk_periods(rows, target_date=datetime(2026, 10, 4).date())

    assert len(periods) == 2
    assert periods[0].start.hour == 10
    assert periods[0].end.hour == 11
    assert periods[0].max_probability == 90
    assert periods[1].start.hour == 13
    assert periods[1].end.hour == 16


def test_rainfall_threshold_triggers_without_high_probability() -> None:
    rows = [_hour(11, 40, 10)]

    periods = find_rain_risk_periods(rows, target_date=datetime(2026, 10, 4).date())

    assert len(periods) == 1
    assert periods[0].max_rainfall_mm == 10


def test_daily_peak_fallback_selects_strongest_low_probability_hour() -> None:
    rows = [
        _hour(10, 20, 1),
        _hour(14, 40, 3),
        _hour(18, 35, 6),
    ]

    peak = find_daily_peak_period(
        rows,
        target_date=datetime(2026, 10, 4).date(),
    )

    assert peak is not None
    assert peak.start.hour == 17
    assert peak.max_probability == 35
    assert peak.max_rainfall_mm == 6


def test_daily_peak_fallback_returns_none_when_day_is_below_minimum() -> None:
    rows = [_hour(14, 25, 2)]

    peak = find_daily_peak_period(
        rows,
        target_date=datetime(2026, 10, 4).date(),
    )

    assert peak is None


def test_daily_peak_uses_location_timezone_for_utc_forecast_rows() -> None:
    row = _hour(0, 40, 3)
    row.valid_time = datetime(2026, 10, 3, 18, tzinfo=timezone.utc)

    peak = find_daily_peak_period(
        [row],
        target_date=datetime(2026, 10, 4).date(),
        timezone_name="Asia/Bangkok",
    )

    assert peak is not None
    assert peak.start == datetime(2026, 10, 3, 17, tzinfo=timezone.utc)


def test_incident_timestamp_labels_preceding_bangkok_hour() -> None:
    row = HourlyForecast(
        valid_time=datetime(2026, 10, 8, 9),
        precipitation_probability=63,
        precipitation=0.2,
    )

    peak = find_daily_peak_period(
        [row],
        target_date=datetime(2026, 10, 8).date(),
        timezone_name="Asia/Bangkok",
    )

    assert peak is not None
    assert peak.start == datetime(2026, 10, 8, 8)
    assert peak.end == row.valid_time


def test_midnight_interval_belongs_to_local_start_day() -> None:
    row = _hour(17, 80, 1)  # 00:00 Bangkok; interval is 23:00-00:00.

    previous_day = find_rain_risk_periods(
        [row],
        target_date=datetime(2026, 10, 4).date(),
        timezone_name="Asia/Bangkok",
    )
    next_day = find_rain_risk_periods(
        [row],
        target_date=datetime(2026, 10, 5).date(),
        timezone_name="Asia/Bangkok",
    )

    assert len(previous_day) == 1
    assert previous_day[0].start == datetime(2026, 10, 4, 16, tzinfo=timezone.utc)
    assert previous_day[0].end == row.valid_time
    assert next_day == []
