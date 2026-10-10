"""P2 adversarial pairing, cutoff, provenance and API regression."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from math import inf, nan

import pytest
from sqlalchemy import func, select

from app.evaluation.audit import AuditPair, audit_pairs, evaluate_location_audit
from app.evaluation.metrics import EvaluationSample, calculate_metrics
from app.models.forecast import ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.observation import Observation

UTC = timezone.utc
START = datetime(2024, 1, 1, tzinfo=UTC)
END = START + timedelta(days=10)
HOUR = timedelta(hours=1)


def pair(**changes):
    row = AuditPair(
        forecast_run_id=1, forecast_row_id=1, location_id=101,
        provider="open_meteo", retrieved_at=START + HOUR,
        valid_time=START + HOUR * 3, variable="precipitation",
        forecast_value=2, probability=75, observation_id=1,
        observation_location_id=101, observed_at=START + HOUR * 3,
        observation_created_at=START + HOUR * 4,
        source="open_meteo_historical", reference_value=1,
    )
    return replace(row, **changes)


def report(rows):
    return audit_pairs(rows, location_id=101, since=START, as_of=END)


def test_proxy_is_explicit_and_never_claims_verified_point_accuracy():
    body = report([pair()])
    assert body["status"] == "proxy_reference_only"
    assert body["accuracy_claim_available"] is False
    assert body["verified_at_point_pairs"] == 0
    assert body["alert_delivery_evaluated"] is False
    metric = body["metrics"][0]
    assert metric["reference_kind"] == "reanalysis"
    assert metric["horizon_basis"] == "period_start"
    assert (metric["mae"], metric["rmse"], metric["bias"]) == (1, 1, 1)
    event = metric["precipitation_occurrence"]
    assert event["hits"] == 1
    assert event["brier_score"] == pytest.approx(0.0625)


@pytest.mark.parametrize("retrieved,eligible", [
    (START + HOUR * 2, True),
    (START + HOUR * 2 + timedelta(microseconds=1), False),
    (START + HOUR * 3, False),
])
def test_precipitation_retrieval_must_precede_whole_hour(retrieved, eligible):
    body = report([pair(retrieved_at=retrieved)])
    assert body["selected_pairs"] == int(eligible)
    if not eligible:
        assert body["excluded_by_reason"] == {"retrieval_after_period_start": 1}


@pytest.mark.parametrize("changes,reason", [
    ({"location_id": 102}, "wrong_forecast_location"),
    ({"variable": "wind_direction_10m"}, "unsupported_variable"),
    ({"valid_time": END + HOUR}, "outside_evaluation_window"),
    ({"observation_id": None}, "missing_reference"),
    ({"observation_location_id": 102}, "wrong_reference_location"),
    ({"observed_at": START + HOUR * 4}, "reference_time_mismatch"),
    ({"provider": "other"}, "unknown_provider_period"),
    ({"source": "station"}, "unknown_reference_provenance"),
    ({"source": "manual"}, "unknown_reference_provenance"),
    ({"observation_created_at": None}, "reference_unavailable_at_cutoff"),
    ({"observation_created_at": END + timedelta(microseconds=1)}, "reference_unavailable_at_cutoff"),
    ({"forecast_value": None}, "missing_or_nonfinite_value"),
    ({"reference_value": nan}, "missing_or_nonfinite_value"),
    ({"forecast_value": inf}, "missing_or_nonfinite_value"),
    ({"forecast_value": True}, "missing_or_nonfinite_value"),
    ({"reference_value": -1}, "negative_precipitation"),
    ({"retrieved_at": START - timedelta(days=20)}, "outside_supported_horizon"),
])
def test_unverified_invalid_or_unavailable_pairs_fail_closed(changes, reason):
    body = report([pair(**changes)])
    assert body["metrics"] == []
    assert body["status"] == "no_eligible_pairs"
    assert body["excluded_by_reason"] == {reason: 1}


def test_same_target_is_selected_once_in_bucket_latest_retrieval_wins():
    rows = [pair(retrieved_at=START, forecast_value=100),
            pair(forecast_run_id=2, forecast_row_id=2, retrieved_at=START + HOUR,
                 forecast_value=2)]
    a, b = report(rows), report(reversed(rows))
    assert a == b
    assert a["eligible_pairs"] == 2
    assert a["selected_pairs"] == 1
    assert a["excluded_by_reason"] == {"duplicate_snapshot_in_bucket": 1}
    assert a["metrics"][0]["mae"] == 1


def test_equal_retrieval_ties_are_deterministic_and_horizons_stay_separate():
    rows = [pair(forecast_value=50),
            pair(forecast_run_id=2, forecast_row_id=2, forecast_value=2),
            pair(forecast_run_id=3, forecast_row_id=3, retrieved_at=START - HOUR * 2,
                 forecast_value=3)]
    body = report(reversed(rows))
    assert body["selected_pairs"] == 2
    assert [(m["horizon_start_hours"], m["mae"]) for m in body["metrics"]] == [(0, 1), (3, 2)]


def test_metrics_and_occurrence_counts_include_hits_misses_and_false_alarms():
    rows = []
    for index, (predicted, actual, probability) in enumerate([
        (2, 1, 75), (2, 0, 75), (0, 1, 25), (0, 0, 25),
    ]):
        valid = START + HOUR * (index + 3)
        rows.append(pair(forecast_run_id=index + 1, forecast_row_id=index + 1,
                         valid_time=valid, retrieved_at=valid - HOUR * 2,
                         observed_at=valid, observation_id=index + 1,
                         observation_created_at=valid + HOUR,
                         forecast_value=predicted, reference_value=actual,
                         probability=probability))
    metric = report(rows)["metrics"][0]
    assert metric["sample_count"] == metric["unique_target_count"] == 4
    assert metric["mae"] == 1
    assert metric["rmse"] == pytest.approx((6 / 4) ** 0.5)
    assert metric["bias"] == 0.5
    event = metric["precipitation_occurrence"]
    assert (event["hits"], event["misses"], event["false_alarms"], event["correct_dry"]) == (1, 1, 1, 1)
    assert event["precision"] == event["recall"] == event["false_alarm_ratio"] == 0.5
    assert event["brier_sample_count"] == 4
    assert event["brier_score"] == pytest.approx(0.3125)


@pytest.mark.parametrize("probability", [None, -1, 101, nan, True])
def test_bad_probability_does_not_discard_amount_but_has_no_brier_score(probability):
    event = report([pair(forecast_value=0, reference_value=0,
                         probability=probability)])["metrics"][0]["precipitation_occurrence"]
    assert event["correct_dry"] == 1
    assert event["precision"] is event["recall"] is event["false_alarm_ratio"] is None
    assert event["brier_sample_count"] == 0
    assert event["brier_score"] is None


def test_precipitation_threshold_is_strict_and_temperature_is_instantaneous():
    assert report([pair(forecast_value=0.1, reference_value=0.1)])["metrics"][0]["precipitation_occurrence"]["correct_dry"] == 1
    body = report([pair(variable="temperature_2m", retrieved_at=START + HOUR * 3,
                        forecast_value=-10, reference_value=-12)])
    assert body["selected_pairs"] == 1
    assert body["metrics"][0]["unit"] == "degC"
    assert body["metrics"][0]["precipitation_occurrence"] is None


def test_timezone_equivalence_and_subsecond_negative_lead_are_preserved():
    offset = timezone(timedelta(hours=7))
    shifted = pair(valid_time=(START + HOUR * 3).astimezone(offset),
                   observed_at=(START + HOUR * 3).astimezone(offset))
    assert report([shifted]) == report([pair()])
    metrics = calculate_metrics([EvaluationSample(
        "temperature_2m", START, START - timedelta(microseconds=1), 2, 1,
    )])
    assert metrics == []


@pytest.mark.parametrize("as_of", [START, START - HOUR])
def test_reversed_or_empty_audit_window_is_rejected(as_of):
    with pytest.raises(ValueError, match="since must precede"):
        audit_pairs([], location_id=101, since=START, as_of=as_of)


async def insert_fixture(db, location_id=None, slug="p2-audit"):
    if location_id is None:
        loc = Location(name=slug, slug=slug, latitude=0, longitude=0,
                       timezone="UTC", provider="open_meteo")
        db.add(loc)
        await db.flush()
        location_id = loc.id
    run = ForecastRun(location_id=location_id, provider="open_meteo",
                      retrieved_at=START + HOUR, forecast_days=1)
    db.add(run)
    await db.flush()
    db.add_all([
        HourlyForecast(forecast_run_id=run.id, valid_time=START + HOUR * 3,
                       temperature_2m=20, precipitation=2, precipitation_probability=75),
        HourlyForecast(forecast_run_id=run.id, valid_time=START + HOUR * 4,
                       temperature_2m=22, precipitation=0),
        Observation(location_id=location_id, observed_at=START + HOUR * 3,
                    source="open_meteo_historical", created_at=START + HOUR * 4,
                    temperature_2m=19, precipitation=1),
    ])
    await db.flush()
    return location_id


@pytest.mark.asyncio
async def test_database_audit_retains_unmatched_rows_and_does_not_write(db_session):
    location_id = await insert_fixture(db_session)
    before = await db_session.scalar(select(func.count()).select_from(Observation))
    body = await evaluate_location_audit(db_session, location_id, since=START, as_of=END)
    assert body["candidate_pairs"] == 4
    assert body["matched_pairs"] == body["selected_pairs"] == 2
    assert body["excluded_by_reason"] == {"missing_reference": 2}
    assert await db_session.scalar(select(func.count()).select_from(Observation)) == before
    assert not db_session.new and not db_session.dirty and not db_session.deleted


@pytest.mark.asyncio
async def test_database_join_never_substitutes_another_locations_observation(db_session):
    first = await insert_fixture(db_session, slug="p2-first")
    second = await insert_fixture(db_session, slug="p2-second")
    own = await db_session.scalar(select(Observation).where(Observation.location_id == first))
    await db_session.delete(own)
    await db_session.flush()
    body = await evaluate_location_audit(db_session, first, since=START, as_of=END)
    assert second != first
    assert body["matched_pairs"] == 0
    assert body["excluded_by_reason"] == {"missing_reference": 4}


@pytest.mark.asyncio
async def test_audit_api_reports_provenance_without_changing_legacy_response(client, db_session):
    location_id = await insert_fixture(db_session, slug="p2-api")
    response = await client.get(f"/api/v1/forecast/{location_id}/evaluation/audit",
                                params={"as_of": END.isoformat(), "days": 10})
    assert response.status_code == 200
    assert response.json()["status"] == "proxy_reference_only"
    assert response.json()["accuracy_claim_available"] is False
    legacy = await client.get(f"/api/v1/forecast/{location_id}/evaluation")
    assert legacy.status_code == 200
    assert set(legacy.json()) == {"location_id", "metrics"}


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [
    {"days": 0}, {"days": 91}, {"as_of": "2024-01-01T00:00:00"},
    {"as_of": "2099-01-01T00:00:00+00:00"},
])
async def test_audit_api_rejects_invalid_window(client, db_session, params):
    location_id = await insert_fixture(db_session, slug="p2-invalid")
    response = await client.get(f"/api/v1/forecast/{location_id}/evaluation/audit", params=params)
    assert response.status_code == 422
