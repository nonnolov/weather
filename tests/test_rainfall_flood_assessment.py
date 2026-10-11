from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.rainfall_flood_assessment import build_rainfall_flood_assessment


UTC = timezone.utc
NOW = datetime(2026, 10, 10, 0, 30, tzinfo=UTC)


def make_run(amounts, *, missing_times=()):
    first_end = datetime(2026, 10, 10, 2, 0, tzinfo=UTC)
    hours = []
    for index, amount in enumerate(amounts):
        valid_time = first_end + timedelta(hours=index)
        hours.append(SimpleNamespace(
            valid_time=valid_time,
            precipitation=None if index in missing_times else amount,
        ))
    return SimpleNamespace(
        id=17,
        location_id=8,
        provider="open_meteo",
        retrieved_at=datetime(2026, 10, 10, 0, 0, tzinfo=UTC),
        hourly_forecasts=hours,
    )


def metric(report, hours):
    return next(item for item in report["rolling_accumulations"] if item["hours"] == hours)


def test_reports_interval_end_semantics_and_rolling_windows():
    report = build_rainfall_flood_assessment(make_run([1] * 24), now=NOW)
    one_hour = metric(report, 1)
    three_hour = metric(report, 3)
    six_hour = metric(report, 6)
    twenty_four_hour = metric(report, 24)

    assert report["data_status"] == "available"
    assert report["forecast_window_start"] == "2026-10-10T01:00:00+00:00"
    assert report["forecast_window_end"] == "2026-10-11T01:00:00+00:00"
    assert report["hourly_precipitation_mm"][0] == {
        "interval_start": "2026-10-10T01:00:00+00:00",
        "interval_end": "2026-10-10T02:00:00+00:00",
        "amount_mm": 1.0,
    }
    assert one_hour["max_accumulation_mm"] == 1
    assert three_hour["max_accumulation_mm"] == 3
    assert six_hour["max_accumulation_mm"] == 6
    assert twenty_four_hour["max_accumulation_mm"] == 24
    assert twenty_four_hour["interval_start"] == "2026-10-10T01:00:00+00:00"
    assert report["assessment_status"] == "not_assessed"
    assert report["measurement_available"] is False
    assert report["flood_occurrence_confirmed"] is False


def test_missing_hour_is_not_replaced_with_zero_and_breaks_overlapping_windows():
    report = build_rainfall_flood_assessment(
        make_run([2] * 24, missing_times={5}), now=NOW,
    )
    assert report["data_status"] == "partial"
    assert report["hours_with_precipitation"] == 23
    assert report["hourly_precipitation_mm"][4]["amount_mm"] == 2
    assert report["hourly_precipitation_mm"][5]["amount_mm"] is None
    assert metric(report, 3)["max_accumulation_mm"] == 6
    assert metric(report, 24)["max_accumulation_mm"] is None
    assert metric(report, 24)["complete_windows"] == 0


def test_time_gap_breaks_rolling_window_instead_of_summing_across_it():
    run = make_run([1] * 24)
    run.hourly_forecasts[4].valid_time += timedelta(hours=1)
    report = build_rainfall_flood_assessment(run, now=NOW)
    assert report["data_status"] == "partial"
    assert metric(report, 3)["max_accumulation_mm"] == 3


def test_negative_non_finite_values_remain_missing():
    report = build_rainfall_flood_assessment(
        make_run([0, -1, float("nan"), float("inf")] + [1] * 20),
        now=NOW,
    )
    assert report["hours_with_precipitation"] == 21
    assert all(row["amount_mm"] is None for row in report["hourly_precipitation_mm"][1:4])


def test_no_fully_future_hour_means_unavailable_not_zero():
    report = build_rainfall_flood_assessment(
        make_run([1]), now=datetime(2026, 10, 10, 1, 30, tzinfo=UTC),
    )
    assert report["data_status"] == "unavailable"
    assert report["hours_expected"] == 0
    assert all(item["max_accumulation_mm"] is None for item in report["rolling_accumulations"])
