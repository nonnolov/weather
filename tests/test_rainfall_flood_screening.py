from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.services.rainfall_flood_assessment import build_rainfall_flood_assessment
from tests.test_rainfall_flood_assessment import NOW, make_run


def location(province="Bangkok", **kwargs):
    return SimpleNamespace(id=8, country_code="TH", province=province,
                           latitude=13.75, longitude=100.5, **kwargs)


def assess(amounts, province="Bangkok", **kwargs):
    return build_rainfall_flood_assessment(
        make_run(amounts), now=NOW, location=location(province), **kwargs)


@pytest.mark.parametrize("province,threshold", [("Bangkok", 40), ("กรุงเทพมหานคร", 40), ("เชียงใหม่", 75)])
@pytest.mark.parametrize("delta,expected", [(-0.0001, False), (0, True), (0.0001, True)])
def test_hourly_thresholds_use_unrounded_values(province, threshold, delta, expected):
    report = assess([threshold + delta] + [0] * 23, province)
    assert report["risk_detected"] is expected
    assert report["risk_level"] == ("watch" if expected else None)
    assert report["historical_validation_status"] == "not_calibrated"


@pytest.mark.parametrize("month,threshold", [(1,150), (4,150), (5,100), (10,100), (11,150)])
@pytest.mark.parametrize("delta,expected", [(-0.01,False), (0,True)])
def test_seasonal_accumulation_boundary(month, threshold, delta, expected):
    run = make_run([0] * 24)
    # Put the exact total in two small hours; hourly trigger remains below 40.
    run.hourly_forecasts = [
        SimpleNamespace(valid_time=row.valid_time.replace(month=month),
                        precipitation=(threshold + delta) / 24)
        for row in run.hourly_forecasts
    ]
    now = NOW.replace(month=month)
    run.retrieved_at = now
    report = build_rainfall_flood_assessment(run, now=now, location=location())
    assert report["risk_detected"] is expected
    assert report["location_profile"]["24h_threshold_mm"] == threshold


def test_partial_data_can_detect_trigger_but_cannot_assert_below_threshold():
    for amount, expected in [(40, True), (39, None)]:
        run = make_run([amount] + [0] * 23, missing_times={10})
        report = build_rainfall_flood_assessment(run, now=NOW, location=location())
        assert report["risk_detected"] is expected
        assert "forecast_horizon_incomplete" in report["assessment_reason_codes"]


@pytest.mark.parametrize("age,reason", [(7,"forecast_stale"), (-1,"forecast_retrieval_in_future")])
def test_invalid_forecast_freshness_blocks_even_extreme_rain(age, reason):
    run = make_run([100] * 24)
    run.retrieved_at = NOW - timedelta(hours=age)
    report = build_rainfall_flood_assessment(run, now=NOW, location=location())
    assert report["risk_detected"] is None
    assert report["assessment_reason_codes"] == [reason]


def test_future_leading_gap_is_not_shifted_out_of_horizon():
    run = make_run([0] * 24)
    run.hourly_forecasts = run.hourly_forecasts[1:]
    report = build_rainfall_flood_assessment(run, now=NOW, location=location())
    assert report["hourly_precipitation_mm"][0]["amount_mm"] is None
    assert report["risk_detected"] is None


def test_location_scope_and_forecast_isolation():
    for loc, reason in [
        (location("Phuket"), "urban_threshold_scope_unverified"),
        (SimpleNamespace(id=99), "location_forecast_mismatch"),
        (SimpleNamespace(id=8, country_code=None), "location_profile_unavailable"),
    ]:
        report = build_rainfall_flood_assessment(make_run([100]*24), now=NOW, location=loc)
        assert report["risk_detected"] is None
        assert report["assessment_reason_codes"] == [reason]


def test_conflicting_duplicate_is_unusable_in_both_orders():
    run = make_run([0] * 24)
    row = SimpleNamespace(valid_time=run.hourly_forecasts[0].valid_time, precipitation=100)
    for rows in [run.hourly_forecasts + [row], [row] + run.hourly_forecasts]:
        copy = SimpleNamespace(**{**vars(run), "hourly_forecasts": rows})
        report = build_rainfall_flood_assessment(copy, now=NOW, location=location())
        assert report["risk_detected"] is None


def test_duration_breaks_at_missing_and_zero_rain():
    report = assess([1,1,0,1,1,1,None] + [0]*17)
    assert report["max_consecutive_rain_hours"] == 3


def test_unsupported_provider_cannot_assume_precipitation_interval_semantics():
    run = make_run([100] * 24)
    run.provider = "other"
    report = build_rainfall_flood_assessment(run, now=NOW, location=location())
    assert report["risk_detected"] is None
    assert report["assessment_reason_codes"] == ["forecast_interval_semantics_unverified"]


def test_season_boundary_uses_thailand_local_end_date():
    run = make_run([110 / 24] * 24)
    start = NOW.replace(month=10, day=30, hour=17, minute=0)
    first_end = start.replace(hour=18)
    for index, row in enumerate(run.hourly_forecasts):
        row.valid_time = first_end + timedelta(hours=index)
    run.retrieved_at = start
    report = build_rainfall_flood_assessment(run, now=start, location=location())
    assert report["location_profile"]["24h_threshold_mm"] == 150
    assert report["risk_detected"] is False
