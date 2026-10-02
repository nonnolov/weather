"""Pure, deterministic forecast-accuracy calculations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import fsum, isfinite, sqrt
from typing import Iterable


@dataclass(frozen=True)
class EvaluationSample:
    """One forecast/observation value pair for a shared valid time."""

    variable: str
    retrieved_at: datetime
    valid_time: datetime
    forecast_value: float | None
    observation_value: float | None


@dataclass(frozen=True)
class ForecastMetric:
    """Accuracy metrics for one variable at one forecast horizon."""

    variable: str
    horizon_hours: float
    sample_count: int
    mae: float
    rmse: float
    bias: float


def calculate_metrics(samples: Iterable[EvaluationSample]) -> list[ForecastMetric]:
    """Calculate MAE, RMSE, and bias from forecast-minus-observation errors.

    Samples without both finite numeric values, or whose valid time predates the
    forecast retrieval, are omitted. Results are sorted so callers receive the
    same output regardless of input ordering.
    """
    grouped: dict[tuple[str, int], list[float]] = {}

    for sample in samples:
        if not _is_finite_number(sample.forecast_value) or not _is_finite_number(sample.observation_value):
            continue

        horizon_seconds = round(
            (_as_utc(sample.valid_time) - _as_utc(sample.retrieved_at)).total_seconds()
        )
        if horizon_seconds < 0:
            continue

        error = float(sample.forecast_value) - float(sample.observation_value)
        grouped.setdefault((sample.variable, horizon_seconds), []).append(error)

    metrics: list[ForecastMetric] = []
    for (variable, horizon_seconds), errors in sorted(grouped.items()):
        ordered_errors = sorted(errors)
        count = len(ordered_errors)
        metrics.append(
            ForecastMetric(
                variable=variable,
                horizon_hours=horizon_seconds / 3600,
                sample_count=count,
                mae=fsum(abs(error) for error in ordered_errors) / count,
                rmse=sqrt(fsum(error * error for error in ordered_errors) / count),
                bias=fsum(ordered_errors) / count,
            )
        )
    return metrics


def _is_finite_number(value: float | None) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _as_utc(value: datetime) -> datetime:
    """Treat database-returned naive timestamps as UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
