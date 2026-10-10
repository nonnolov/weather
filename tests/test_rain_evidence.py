import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.evaluation.rain_cli import main
from app.evaluation.rain_evidence import (
    collect_station, evaluate_point_rain, record_point, save_json, stage_station, validate_point,
)

START = datetime(2026, 10, 10, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=1)
CUTOFF = START + timedelta(hours=8)


def reference(**changes):
    return dict(template_only=False, report_id="actual-report-1", scope_id="point-a",
                observation_type="continuous_interval", rain_status="raining",
                recorded_at=(END + timedelta(minutes=5)).isoformat(),
                coverage_start=START.isoformat(), coverage_end=END.isoformat(),
                rainfall_mm=None, **changes) if not changes else {**reference(), **changes}


def forecast(**changes):
    return {**dict(scope_id="point-a", provider="open_meteo", run_id=1, row_id=1,
                   valid_time=END.isoformat(), retrieved_at=(START - timedelta(hours=1)).isoformat(),
                   rain_mm=1.0), **changes}


def evaluate(forecasts=None, references=None):
    return evaluate_point_rain(forecasts if forecasts is not None else [forecast()],
                               references if references is not None else [reference()],
                               scope_id="point-a", since=START, as_of=CUTOFF)


@pytest.mark.parametrize("value,quality", [(None, "missing"), (0, "plausible_amount"),
    (0.8, "plausible_amount"), (-1, "invalid_amount"), (True, "invalid_amount"),
    ("0", "invalid_amount"), (float("nan"), "invalid_amount")])
def test_station_values_never_fill_gaps_or_claim_alignment(value, quality):
    data = stage_station({"result": "OK", "data": [
        {"rainfall_datetime": "2026-10-10 23:00", "rainfall_value": value}]},
        b"raw-response", collected_at=CUTOFF)
    assert data["rows"][0]["quality"] == quality
    assert data["rows"][0]["provider_time"] == "2026-10-10 23:00"
    assert not data["evaluation_eligible"] and not data["alignment_verified"]
    assert data["raw_sha256"] and data["raw_response"]["data"][0]["rainfall_value"] is value


@pytest.mark.parametrize("payload", [[], {"result": "ERROR", "data": []},
    {"result": "OK", "data": None}, {"result": "OK", "data": [{}]}])
def test_station_contract_drift_rejected(payload):
    with pytest.raises(ValueError):
        stage_station(payload, b"raw", collected_at=CUTOFF)


@pytest.mark.parametrize("changes", [
    {"template_only": True}, {"scope_id": ""}, {"recorded_at": "2026-10-10T04:00:00"},
    {"coverage_end": (END + timedelta(minutes=30)).isoformat()},
    {"recorded_at": START.isoformat()}, {"rain_status": "unknown"},
    {"rainfall_mm": 0}, {"observation_type": "point_check"},
    {"coverage_start": END.isoformat()},
])
def test_invalid_manual_reports_rejected(changes):
    with pytest.raises(ValueError):
        validate_point(reference(**changes))


def test_timezone_equivalence_and_immutable_record(tmp_path):
    row = reference(coverage_start="2026-10-10T07:00:00+07:00",
                    coverage_end="2026-10-10T08:00:00+07:00")
    first = record_point(row, tmp_path)
    second = record_point(row, tmp_path)
    assert first == second and len(list(tmp_path.iterdir())) == 1
    assert json.loads(first.read_text())["coverage_end"] == END.isoformat()


@pytest.mark.parametrize("rain,status,outcome", [
    (1, "raining", "hits"), (0, "raining", "misses"),
    (1, "not_raining", "false_alarms"), (0, "not_raining", "correct_dry"),
])
def test_all_occurrence_outcomes(rain, status, outcome):
    report = evaluate([forecast(rain_mm=rain)], [reference(rain_status=status)])
    metric = report["metrics"][0]
    assert metric[outcome] == 1 and metric["sample_count"] == 1
    assert report["amount_metrics"] is None and report["probability_metrics"] is None
    assert not report["accuracy_claim_available"] and not report["alert_delivery_evaluated"]


def test_zero_denominators_stay_null():
    metric = evaluate([forecast(rain_mm=0)], [reference(rain_status="not_raining")])["metrics"][0]
    assert metric["precision"] is metric["recall"] is metric["false_alarm_ratio"] is None


@pytest.mark.parametrize("changes,reason", [
    ({"scope_id": "point-b"}, "different_reference_scope"),
    ({"rain_status": "not_observed"}, "unobserved_interval"),
    ({"recorded_at": (CUTOFF + timedelta(seconds=1)).isoformat()}, "reference_unavailable_at_cutoff"),
    ({"observation_type": "point_check", "coverage_start": END.isoformat()}, "point_check_not_hourly_coverage"),
])
def test_ineligible_reference_cannot_score(changes, reason):
    report = evaluate(references=[reference(**changes)])
    assert report["selected_pairs"] == 0 and report["excluded_by_reason"][reason] == 1


@pytest.mark.parametrize("changes,reason", [
    ({"scope_id": "point-b"}, "different_forecast_scope"),
    ({"provider": "other"}, "unknown_forecast_period"),
    ({"retrieved_at": (START + timedelta(microseconds=1)).isoformat()}, "forecast_retrieved_after_period_start"),
    ({"rain_mm": None}, "invalid_forecast_rain_amount"),
    ({"rain_mm": -1}, "invalid_forecast_rain_amount"),
    ({"rain_mm": True}, "invalid_forecast_rain_amount"),
    ({"run_id": True}, "invalid_forecast"),
    ({"retrieved_at": (START - timedelta(hours=384)).isoformat()}, "unsupported_forecast_lead"),
])
def test_ineligible_forecast_cannot_score(changes, reason):
    report = evaluate(forecasts=[forecast(**changes)])
    assert report["selected_pairs"] == 0 and report["excluded_by_reason"][reason] == 1


def test_conflicting_and_duplicate_references():
    report = evaluate(references=[reference(), reference(report_id="2", rain_status="not_raining")])
    assert report["selected_pairs"] == 0
    assert report["excluded_by_reason"]["conflicting_reference_interval"] == 2
    duplicate = evaluate(references=[reference(), reference()])
    assert duplicate["selected_pairs"] == 1
    assert duplicate["excluded_by_reason"]["duplicate_reference_interval"] == 1


def test_latest_snapshot_and_order_do_not_inflate_counts():
    rows = [forecast(rain_mm=0), forecast(run_id=2, row_id=2,
        retrieved_at=(START - timedelta(minutes=1)).isoformat())]
    assert evaluate(rows) == evaluate(list(reversed(rows)))
    report = evaluate(rows)
    assert report["metrics"][0]["hits"] == 1
    assert report["excluded_by_reason"]["duplicate_forecast_in_bucket"] == 1


def test_conflicting_snapshot_fails_instead_of_silently_selecting():
    with pytest.raises(ValueError, match="Conflicting immutable"):
        evaluate([forecast(), forecast(rain_mm=0)])


def test_separate_horizon_buckets_report_unique_hours():
    rows = [forecast(), forecast(run_id=2, row_id=2, retrieved_at=(START - timedelta(hours=6)).isoformat())]
    report = evaluate(rows)
    assert len(report["metrics"]) == 2 and report["selected_pairs"] == 2
    assert report["unique_target_count"] == 1


def test_period_boundary_and_empty_window():
    report = evaluate_point_rain([forecast()], [reference()], scope_id="point-a",
        since=START + timedelta(microseconds=1), as_of=CUTOFF)
    assert report["selected_pairs"] == 0
    with pytest.raises(ValueError):
        evaluate_point_rain([], [], scope_id="point-a", since=CUTOFF, as_of=CUTOFF)


def test_report_cli_file_to_report(tmp_path, capsys):
    forecasts, refs, out = (tmp_path / name for name in ("forecast.json", "reference.json", "report.json"))
    save_json(forecasts, [forecast()])
    save_json(refs, [reference(rain_status="not_raining")])
    main(["report", "--forecasts", str(forecasts), "--references", str(refs),
          "--scope-id", "point-a", "--since", START.isoformat(), "--as-of", CUTOFF.isoformat(),
          "--output", str(out)])
    report = json.loads(out.read_text())
    assert report["metrics"][0]["false_alarms"] == 1
    assert "point-a" not in out.read_text()
    assert json.loads(capsys.readouterr().out)["selected_pairs"] == 1


def test_collector_preserves_repeated_fetches_and_corrections(tmp_path, monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, params):
            assert params == {"station_id": 1116457}
            return httpx.Response(200, json={"result": "OK", "data": [
                {"rainfall_datetime": "2026-10-10 23:00", "rainfall_value": None}]},
                request=httpx.Request("GET", url))
    monkeypatch.setattr("app.evaluation.rain_evidence.httpx.Client", Client)
    first, _ = collect_station(tmp_path)
    second, _ = collect_station(tmp_path)
    assert first != second and len(list(tmp_path.iterdir())) == 2
    assert json.loads(first.read_text())["missing_rows"] == 1



def test_conflicting_snapshot_is_rejected_before_later_snapshot_can_hide_it():
    rows = [forecast(), forecast(run_id=2, row_id=2,
            retrieved_at=START.isoformat()), forecast(rain_mm=2)]
    for ordering in (rows, list(reversed(rows))):
        with pytest.raises(ValueError, match="Conflicting immutable"):
            evaluate(ordering)


def test_same_report_identity_cannot_change_its_rain_state():
    with pytest.raises(ValueError, match="Conflicting immutable point report"):
        evaluate(references=[reference(), reference(rain_status="not_raining")])


def test_station_cannot_masquerade_as_manual_point_report():
    with pytest.raises(ValueError):
        validate_point(reference(source="thaiwater_graph"))


def test_record_cli_and_bad_input_preserve_existing_evidence(tmp_path, capsys):
    source, directory = tmp_path / "input.json", tmp_path / "evidence"
    save_json(source, reference())
    main(["record-point", "--input", str(source), "--directory", str(directory)])
    assert json.loads(capsys.readouterr().out)["recorded"] is True
    existing = list(directory.iterdir())
    save_json(source, reference(template_only=True))
    with pytest.raises(ValueError):
        main(["record-point", "--input", str(source), "--directory", str(directory)])
    assert list(directory.iterdir()) == existing


def test_empty_scope_rejected():
    with pytest.raises(ValueError):
        evaluate_point_rain([], [], scope_id="", since=START, as_of=CUTOFF)
