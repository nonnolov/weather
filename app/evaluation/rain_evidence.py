"""Offline measured-rain evidence. No database writes, schedulers or LINE calls.

A staged ThaiWater graph is never promoted to aligned measurements here.
Manual continuous reports score any visible rain, not an invented millimeter
threshold. Their scores remain self-report comparisons, not certified accuracy.
"""
import hashlib
import json
import math
import os
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx

ENDPOINT = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h_graph"
STATION_ID = 1116457
LEAD_EDGES = (0, 3, 6, 12, 24, 48, 72, 168, 384)


def aware(value):
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Explicit timezone required")
    return result.astimezone(timezone.utc)


def finite_amount(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def stage_station(payload, raw_bytes, *, collected_at):
    """Preserve provider clock and gaps without guessing timezone or period."""
    if not isinstance(payload, dict) or payload.get("result") != "OK" or not isinstance(payload.get("data"), list):
        raise ValueError("Unexpected ThaiWater graph response")
    rows = []
    for row in payload["data"]:
        if not isinstance(row, dict) or not isinstance(row.get("rainfall_datetime"), str):
            raise ValueError("Unexpected ThaiWater row")
        value = row.get("rainfall_value")
        rows.append({"provider_time": row["rainfall_datetime"], "raw_rainfall_value": value,
                     "quality": "missing" if value is None else ("plausible_amount" if finite_amount(value) else "invalid_amount")})
    return {"version": "rain-staging-v1", "station_id": STATION_ID,
            "endpoint": ENDPOINT + "?station_id=" + str(STATION_ID),
            "collected_at": aware(collected_at).isoformat(),
            "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "raw_response": payload, "rows": rows,
            "known_rows": sum(r["quality"] == "plausible_amount" for r in rows),
            "missing_rows": sum(r["quality"] == "missing" for r in rows),
            "invalid_rows": sum(r["quality"] == "invalid_amount" for r in rows),
            "alignment_verified": False, "station_is_at_user_point": False,
            "evaluation_eligible": False,
            "blocked_by": ["endpoint_timezone_unverified", "endpoint_accumulation_interval_unverified",
                           "station_is_not_current_point"],
            "instrument_quality_verified": False}


def save_json(path, data):
    """Atomic output; callers must use private paths for point/forecast inputs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(body)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collect_station(directory):
    """One bounded public GET; save each fetch separately, including corrections."""
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        response = client.get(ENDPOINT, params={"station_id": STATION_ID})
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("Unexpectedly large station response")
        collected_at = datetime.now(timezone.utc)
        data = stage_station(response.json(), response.content, collected_at=collected_at)
    name = collected_at.strftime("%Y%m%dT%H%M%S%fZ") + "-" + data["raw_sha256"][:12] + "-" + uuid4().hex + ".json"
    path = Path(directory) / name
    if path.exists():
        raise FileExistsError(path)
    save_json(path, data)
    return path, data


def validate_point(row):
    """Validate provenance/coverage, retaining point checks as unscored evidence."""
    required = ("report_id", "scope_id", "observation_type", "rain_status", "recorded_at")
    if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip() for k in required):
        raise ValueError("Missing report identity, scope or observation metadata")
    if row.get("template_only") is not False:
        raise ValueError("Templates are not observations")
    if row["observation_type"] not in {"point_check", "continuous_interval"}:
        raise ValueError("Unknown observation type")
    if row["rain_status"] not in {"raining", "not_raining", "not_observed"}:
        raise ValueError("Unknown rain status")
    if row.get("source", "manual_point_report") != "manual_point_report":
        raise ValueError("Only explicitly manual reports are supported")
    result = dict(row)
    recorded = aware(row["recorded_at"])
    result["recorded_at"] = recorded.isoformat()
    start, end = aware(row["coverage_start"]), aware(row["coverage_end"])
    if start > end or end > recorded:
        raise ValueError("Coverage must be ordered and end no later than recording")
    if row["observation_type"] == "point_check" and start != end:
        raise ValueError("Point checks must have zero interval coverage")
    if row["observation_type"] == "continuous_interval" and end - start != timedelta(hours=1):
        raise ValueError("Only explicit whole-hour continuous reports are supported")
    if row["observation_type"] == "continuous_interval" and (end.minute or end.second or end.microsecond):
        raise ValueError("Continuous coverage must align with forecast hour boundaries")
    if row.get("rainfall_mm") is not None:
        raise ValueError("Manual rain-state reports cannot supply unverified millimeters")
    result.update(coverage_start=start.isoformat(), coverage_end=end.isoformat(),
                  source="manual_point_report", reference_kind="self_report",
                  rainfall_mm=None, independent_quality_verified=False)
    return result


def record_point(row, directory):
    checked = validate_point(row)
    body = json.dumps(checked, sort_keys=True, allow_nan=False).encode()
    digest = hashlib.sha256(body).hexdigest()
    path = Path(directory) / (digest + ".json")
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != checked:
            raise ValueError("Evidence hash collision")
        return path
    save_json(path, checked)
    return path


def evaluate_point_rain(forecasts, references, *, scope_id, since, as_of):
    """Exact same-point hourly comparisons. No nearby-station or proxy merging.

    A continuous 'raining' report means some rain occurred within the hour.
    A continuous 'not_raining' report means none occurred throughout it.
    Manual visual reports use any rain; Open-Meteo rain amount >0 is the
    prediction. PoP's >0.1mm precipitation definition is not scored against
    visual reports. Numeric amount errors are therefore unavailable here.
    """
    if not isinstance(scope_id, str) or not scope_id.strip():
        raise ValueError("Explicit evaluation scope required")
    since, as_of = aware(since), aware(as_of)
    if since >= as_of:
        raise ValueError("since must precede as_of")
    excluded = Counter()
    index = defaultdict(list)
    reference_count = 0
    reference_ids = {}
    for raw in references:
        reference_count += 1
        try:
            row = validate_point(raw)
        except (ValueError, TypeError, KeyError):
            excluded["invalid_reference"] += 1
            continue
        identity = (row["scope_id"], row["coverage_start"], row["coverage_end"], row["rain_status"], row["observation_type"], row["recorded_at"])
        previous_identity = reference_ids.setdefault(row["report_id"], identity)
        if previous_identity != identity:
            raise ValueError("Conflicting immutable point report")
        start, end = aware(row["coverage_start"]), aware(row["coverage_end"])
        if row["scope_id"] != scope_id:
            reason = "different_reference_scope"
        elif row["observation_type"] != "continuous_interval":
            reason = "point_check_not_hourly_coverage"
        elif row["rain_status"] == "not_observed":
            reason = "unobserved_interval"
        elif not since <= start < end <= as_of:
            reason = "reference_outside_window"
        elif aware(row["recorded_at"]) > as_of:
            reason = "reference_unavailable_at_cutoff"
        else:
            index[end].append(row)
            reason = None
        if reason:
            excluded[reason] += 1
    actual = {}
    for end, rows in index.items():
        states = {r["rain_status"] for r in rows}
        if len(states) > 1:
            excluded["conflicting_reference_interval"] += len(rows)
        else:
            actual[end] = states.pop() == "raining"
            excluded["duplicate_reference_interval"] += len(rows) - 1
    selected = {}
    candidate_count = 0
    forecast_ids = {}
    for row in forecasts:
        candidate_count += 1
        try:
            end, retrieved = aware(row["valid_time"]), aware(row["retrieved_at"])
            start = end - timedelta(hours=1)
            amount = row["rain_mm"]
            if row["scope_id"] != scope_id:
                reason = "different_forecast_scope"
            elif row.get("provider") != "open_meteo":
                reason = "unknown_forecast_period"
            elif not since <= start < end <= as_of:
                reason = "forecast_outside_window"
            elif retrieved > start:
                reason = "forecast_retrieved_after_period_start"
            elif not finite_amount(amount):
                reason = "invalid_forecast_rain_amount"
            elif end not in actual:
                reason = "missing_eligible_reference"
            else:
                lead = (start - retrieved).total_seconds() / 3600
                bucket = next(((a, b) for a, b in zip(LEAD_EDGES, LEAD_EDGES[1:]) if a <= lead < b), None)
                reason = None if bucket else "unsupported_forecast_lead"
            if reason is None:
                run_id, row_id = row["run_id"], row["row_id"]
                if any(not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in (run_id, row_id)):
                    raise ValueError("Invalid snapshot identity")
                identity = (end, retrieved, amount)
                old_identity = forecast_ids.setdefault((run_id, row_id), identity)
                if old_identity != identity:
                    raise ValueError("Conflicting immutable forecast snapshot")
                key = (bucket, end)
                rank = (retrieved, run_id, row_id)
                candidate = (rank, amount > 0, actual[end])
                previous = selected.get(key)
                if previous is not None:
                    excluded["duplicate_forecast_in_bucket"] += 1
                    if rank == previous[0] and candidate != previous:
                        raise ValueError("Conflicting immutable forecast snapshot")
                if previous is None or rank > previous[0]:
                    selected[key] = candidate
        except (ValueError, TypeError, KeyError, StopIteration) as exc:
            if str(exc) == "Conflicting immutable forecast snapshot":
                raise
            reason = "invalid_forecast"
        if reason:
            excluded[reason] += 1
    groups = defaultdict(Counter)
    targets = defaultdict(set)
    for (bucket, end), (_, predicted, observed) in selected.items():
        outcome = ("hits" if observed else "false_alarms") if predicted else ("misses" if observed else "correct_dry")
        groups[bucket][outcome] += 1
        targets[bucket].add(end)
    metrics = []
    for (low, high), counts in sorted(groups.items()):
        hit, false, miss = counts["hits"], counts["false_alarms"], counts["misses"]
        metrics.append({"horizon_start_hours": low, "horizon_end_hours": high,
                        "sample_count": sum(counts.values()), "unique_target_count": len(targets[(low, high)]),
                        **{k: counts[k] for k in ("hits", "false_alarms", "misses", "correct_dry")},
                        "precision": hit / (hit + false) if hit + false else None,
                        "recall": hit / (hit + miss) if hit + miss else None,
                        "false_alarm_ratio": false / (hit + false) if hit + false else None})
    return {"version": "point-rain-evaluation-v1", "since": since.isoformat(), "as_of": as_of.isoformat(),
            "status": "self_report_comparison" if metrics else "no_eligible_pairs",
            "reference_kind": "self_report", "event_definition": "any_rain_during_complete_hour",
            "forecast_variable": "rain", "forecast_event_threshold_mm": 0,
            "amount_metrics": None, "probability_metrics": None,
            "accuracy_claim_available": False, "alert_delivery_evaluated": False,
            "reference_rows": reference_count, "eligible_unique_reference_hours": len(actual),
            "candidate_forecasts": candidate_count, "selected_pairs": len(selected),
            "unique_target_count": len({end for _, end in selected}),
            "excluded_by_reason": {k: v for k, v in sorted(excluded.items()) if v},
            "metrics": metrics,
            "limitations": ["Manual continuous coverage is self-reported, not instrument verified.",
                            "No millimeter or >0.1mm probability calibration from visual reports.",
                            "Targets may appear in different lead buckets; do not sum them as independent hours.",
                            "Point checks, missing hours and nearby stations cannot establish a dry hour."]}
