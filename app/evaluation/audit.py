"""Read-only P2 evaluation with explicit reference and hourly-period semantics.

Open-Meteo archive is a reanalysis reference, not verified at-point measurement.
An amount comparison or rain classification here is not an alert-delivery score.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import fsum, hypot, isfinite, sqrt

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import ForecastRun, HourlyForecast
from app.models.observation import Observation

AUDIT_VERSION = "forecast-audit-v1"
VARIABLES = ("temperature_2m", "precipitation")
HORIZON_EDGES = (0, 3, 6, 12, 24, 48, 72, 168, 384)
PRECIPITATION_EVENT_MM = 0.1


@dataclass(frozen=True)
class AuditPair:
    forecast_run_id: int
    forecast_row_id: int
    location_id: int
    provider: str
    retrieved_at: datetime
    valid_time: datetime
    variable: str
    forecast_value: float | None
    probability: float | None = None
    observation_id: int | None = None
    observation_location_id: int | None = None
    observed_at: datetime | None = None
    observation_created_at: datetime | None = None
    source: str | None = None
    reference_value: float | None = None


def _utc(value: datetime) -> datetime:
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None
            else value.astimezone(timezone.utc))


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _bucket(seconds: float) -> tuple[int, int] | None:
    for start, end in zip(HORIZON_EDGES, HORIZON_EDGES[1:]):
        if start * 3600 <= seconds < end * 3600:
            return start, end
    return None


def _precipitation_metrics(rows: list[AuditPair]) -> dict:
    counts = Counter()
    brier = []
    for row in rows:
        predicted = row.forecast_value > PRECIPITATION_EVENT_MM
        occurred = row.reference_value > PRECIPITATION_EVENT_MM
        counts[("hit" if occurred else "false_alarm") if predicted
               else ("miss" if occurred else "correct_dry")] += 1
        if _finite(row.probability) and 0 <= row.probability <= 100:
            brier.append((row.probability / 100 - int(occurred)) ** 2)
    hits, misses, false = counts["hit"], counts["miss"], counts["false_alarm"]
    return {
        "event_threshold_mm": PRECIPITATION_EVENT_MM,
        "hits": hits, "misses": misses, "false_alarms": false,
        "correct_dry": counts["correct_dry"],
        "precision": hits / (hits + false) if hits + false else None,
        "recall": hits / (hits + misses) if hits + misses else None,
        "false_alarm_ratio": false / (hits + false) if hits + false else None,
        "brier_sample_count": len(brier),
        "brier_score": fsum(brier) / len(brier) if brier else None,
    }


def audit_pairs(pairs, *, location_id: int, since: datetime, as_of: datetime) -> dict:
    """Select one latest retrieval per target/provider/reference/horizon bucket.

    Retrieval must precede the entire accumulated precipitation period, not
    merely its ending timestamp. Targets and reference availability must be
    within the fixed audit cutoff. Unknown provenance is excluded, not guessed.
    """
    since, as_of = _utc(since), _utc(as_of)
    if since >= as_of:
        raise ValueError("since must precede as_of")
    excluded, sources = Counter(), Counter()
    selected = {}
    candidates = matched = eligible = 0
    for row in pairs:
        candidates += 1
        source = row.source or "missing"
        sources[source] += 1
        valid, retrieved = _utc(row.valid_time), _utc(row.retrieved_at)
        period_start = valid - timedelta(hours=1) if row.variable == "precipitation" else valid
        if row.location_id != location_id:
            reason = "wrong_forecast_location"
        elif row.variable not in VARIABLES:
            reason = "unsupported_variable"
        elif not since <= period_start <= valid <= as_of:
            reason = "outside_evaluation_window"
        elif row.observation_id is None:
            reason = "missing_reference"
        elif row.observation_location_id != location_id:
            reason = "wrong_reference_location"
        elif row.observed_at is None or _utc(row.observed_at) != valid:
            reason = "reference_time_mismatch"
        else:
            matched += 1
            if row.provider != "open_meteo":
                reason = "unknown_provider_period"
            elif row.source != "open_meteo_historical":
                reason = "unknown_reference_provenance"
            elif row.observation_created_at is None or _utc(row.observation_created_at) > as_of:
                reason = "reference_unavailable_at_cutoff"
            elif retrieved > period_start:
                reason = "retrieval_after_period_start"
            elif not _finite(row.forecast_value) or not _finite(row.reference_value):
                reason = "missing_or_nonfinite_value"
            elif row.variable == "precipitation" and min(row.forecast_value, row.reference_value) < 0:
                reason = "negative_precipitation"
            elif not isfinite(row.forecast_value - row.reference_value):
                reason = "nonfinite_error"
            elif _bucket((period_start - retrieved).total_seconds()) is None:
                reason = "outside_supported_horizon"
            else:
                reason = None
        if reason:
            excluded[reason] += 1
            continue
        eligible += 1
        bucket = _bucket((period_start - retrieved).total_seconds())
        key = (row.provider, row.source, row.variable, bucket, valid)
        rank = (retrieved, row.forecast_run_id, row.forecast_row_id)
        previous = selected.get(key)
        if previous is None or rank > previous[0]:
            selected[key] = rank, row
    excluded["duplicate_snapshot_in_bucket"] = eligible - len(selected)
    groups = defaultdict(list)
    for key, (_, row) in sorted(selected.items()):
        groups[key[:4]].append(row)
    metrics = []
    for (provider, source, variable, (start, end)), rows in sorted(groups.items()):
        errors = [float(row.forecast_value) - float(row.reference_value) for row in rows]
        count = len(errors)
        metrics.append({
            "provider": provider, "reference_source": source, "reference_kind": "reanalysis",
            "variable": variable, "unit": "mm" if variable == "precipitation" else "degC",
            "horizon_start_hours": start, "horizon_end_hours": end,
            "horizon_basis": "period_start" if variable == "precipitation" else "valid_time",
            "sample_count": count, "unique_target_count": len({_utc(r.valid_time) for r in rows}),
            "mae": fsum(abs(error) / count for error in errors),
            "rmse": hypot(*(error / sqrt(count) for error in errors)),
            "bias": fsum(error / count for error in errors),
            "precipitation_occurrence": _precipitation_metrics(rows) if variable == "precipitation" else None,
        })
    return {
        "audit_version": AUDIT_VERSION, "location_id": location_id,
        "since": since, "as_of": as_of,
        "status": "proxy_reference_only" if metrics else "no_eligible_pairs",
        "accuracy_claim_available": False, "verified_at_point_pairs": 0,
        "alert_delivery_evaluated": False,
        "selection_policy": "latest_retrieval_per_target_provider_reference_horizon_bucket",
        "horizon_basis": "retrieval_time_not_model_initialization",
        "candidate_pairs": candidates, "matched_pairs": matched, "eligible_pairs": eligible,
        "selected_pairs": len(selected),
        "excluded_by_reason": {k: v for k, v in sorted(excluded.items()) if v},
        "reference_sources": dict(sorted(sources.items())),
        "metrics": metrics,
    }


async def evaluate_location_audit(
    db: AsyncSession, location_id: int, *, since: datetime, as_of: datetime
) -> dict:
    """Read immutable snapshots and exact location/time references; no writes."""
    since, as_of = _utc(since), _utc(as_of)
    if since >= as_of:
        raise ValueError("since must precede as_of")
    statement = (
        select(HourlyForecast, ForecastRun, Observation)
        .join(ForecastRun, HourlyForecast.forecast_run_id == ForecastRun.id)
        .outerjoin(Observation, and_(
            Observation.location_id == ForecastRun.location_id,
            Observation.observed_at == HourlyForecast.valid_time,
        ))
        .where(ForecastRun.location_id == location_id,
               HourlyForecast.valid_time >= since, HourlyForecast.valid_time <= as_of)
        .order_by(HourlyForecast.valid_time, ForecastRun.retrieved_at, ForecastRun.id)
    )
    with db.no_autoflush:
        rows = (await db.execute(statement)).tuples().all()
    pairs = (
        AuditPair(
            forecast_run_id=run.id, forecast_row_id=hour.id, location_id=run.location_id,
            provider=run.provider, retrieved_at=run.retrieved_at, valid_time=hour.valid_time,
            variable=variable, forecast_value=getattr(hour, variable),
            probability=hour.precipitation_probability if variable == "precipitation" else None,
            observation_id=obs.id if obs else None,
            observation_location_id=obs.location_id if obs else None,
            observed_at=obs.observed_at if obs else None,
            observation_created_at=obs.created_at if obs else None,
            source=obs.source if obs else None,
            reference_value=getattr(obs, variable) if obs else None,
        )
        for hour, run, obs in rows for variable in VARIABLES
    )
    return audit_pairs(pairs, location_id=location_id, since=since, as_of=as_of)
