from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

from app.services.rainfall_flood_screening import evaluate_rainfall_screening


HORIZONS_HOURS = (1, 3, 6, 24)
FORECAST_HOURS = 24


def _as_utc(value: datetime) -> datetime:
    # SQLite may return a naive datetime for a column declared timezone-aware.
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _finite_nonnegative(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number >= 0 else None


def build_rainfall_flood_assessment(
    run: Any,
    *,
    now: datetime | None = None,
    location: Any = None,
) -> dict[str, Any]:
    """Summarize forecast rainfall exposure without claiming flood probability.

    Open-Meteo's hourly precipitation is the sum over the preceding hour and
    valid_time labels that interval's end. The report therefore preserves
    [valid_time - 1 hour, valid_time] for every value and only aggregates
    consecutive, fully future hourly intervals.
    """
    observed_now = _as_utc(now or datetime.now(timezone.utc))
    by_end: dict[datetime, float | None] = {}
    for row in run.hourly_forecasts:
        end = _as_utc(row.valid_time)
        amount = _finite_nonnegative(row.precipitation)
        # Conflicting duplicates are unusable regardless of input ordering.
        by_end[end] = None if end in by_end and by_end[end] != amount else amount

    future_ends = sorted(
        end for end in by_end
        if end > observed_now and end - timedelta(hours=1) >= observed_now
    )
    start = observed_now.replace(minute=0, second=0, microsecond=0)
    if start < observed_now:
        start += timedelta(hours=1)
    first_end = start + timedelta(hours=1) if future_ends else None
    expected_ends = [
        first_end + timedelta(hours=index) for index in range(FORECAST_HOURS)
    ] if first_end else []

    values = [by_end.get(end) for end in expected_ends]
    steps_available = sum(value is not None for value in values)
    expected_steps = len(expected_ends)
    metrics: list[dict[str, Any]] = []
    for hours in HORIZONS_HOURS:
        expected_windows = max(0, FORECAST_HOURS - hours + 1)
        complete: list[tuple[float, int]] = []
        for start in range(expected_windows):
            window = values[start:start + hours]
            if len(window) == hours and all(amount is not None for amount in window):
                complete.append((sum(amount for amount in window if amount is not None), start))
        peak = max(complete, default=None, key=lambda item: item[0])
        metrics.append({
            "hours": hours,
            "max_accumulation_mm": round(peak[0], 3) if peak else None,
            "interval_start": (
                (expected_ends[peak[1]] - timedelta(hours=1)).isoformat()
                if peak else None
            ),
            "interval_end": (
                expected_ends[peak[1] + hours - 1].isoformat()
                if peak else None
            ),
            "complete_windows": len(complete),
            "expected_windows": expected_windows,
        })

    if expected_steps == FORECAST_HOURS and steps_available == FORECAST_HOURS:
        data_status = "available"
    elif expected_steps:
        data_status = "partial"
    else:
        data_status = "unavailable"

    return {
        "location_id": run.location_id,
        "forecast_run_id": run.id,
        "provider": run.provider,
        "retrieved_at": _as_utc(run.retrieved_at).isoformat(),
        "assessment_method": "local_rainfall_duration_flood_potential_v1",
        **evaluate_rainfall_screening(run, location, values, expected_ends, observed_now),
        "data_status": data_status,
        "forecast_window_start": (
            (first_end - timedelta(hours=1)).isoformat() if first_end else None
        ),
        "forecast_window_end": expected_ends[-1].isoformat() if expected_ends else None,
        "hours_expected": expected_steps,
        "hours_with_precipitation": steps_available,
        "hourly_precipitation_mm": [
            {
                "interval_start": (end - timedelta(hours=1)).isoformat(),
                "interval_end": end.isoformat(),
                "amount_mm": round(amount, 3) if amount is not None else None,
            }
            for end, amount in zip(expected_ends, values)
        ],
        "rolling_accumulations": metrics,
        "source_type": "forecast_model_estimate",
        "measurement_available": False,
        "flood_occurrence_confirmed": False,
    }
