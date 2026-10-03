"""Deterministic, leakage-safe local temperature bias correction."""
from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite, sqrt
from typing import Iterable

from app.evaluation.metrics import EvaluationSample


MIN_TRAIN_SAMPLES = 2
MIN_TEST_SAMPLES = 1


@dataclass(frozen=True)
class TemperatureCorrection:
    """Selected local correction and held-out baseline comparison."""

    variable: str
    model: str | None
    selected: bool
    intercept: float
    slope: float
    train_count: int
    test_count: int
    baseline_mae: float | None
    corrected_mae: float | None
    baseline_rmse: float | None
    corrected_rmse: float | None
    baseline_bias: float | None
    corrected_bias: float | None

    def predict(self, forecast_value: float | None) -> float | None:
        if not self.selected or not _is_finite(forecast_value):
            return forecast_value
        return self.intercept + self.slope * float(forecast_value)


def fit_temperature_correction(samples: Iterable[EvaluationSample]) -> TemperatureCorrection:
    """Fit only earlier samples; select correction only on later held-out MAE."""
    rows = sorted(
        (
            sample
            for sample in samples
            if sample.variable == "temperature_2m"
            and _is_finite(sample.forecast_value)
            and _is_finite(sample.observation_value)
            and _utc_timestamp(sample.valid_time) >= _utc_timestamp(sample.retrieved_at)
        ),
        key=lambda sample: (_utc_timestamp(sample.valid_time), _utc_timestamp(sample.retrieved_at)),
    )
    if len(rows) < MIN_TRAIN_SAMPLES + MIN_TEST_SAMPLES:
        return _baseline(train_count=0, test_count=0)

    split = max(MIN_TRAIN_SAMPLES, len(rows) * 4 // 5)
    if len(rows) - split < MIN_TEST_SAMPLES:
        split = len(rows) - MIN_TEST_SAMPLES
    train, test = rows[:split], rows[split:]
    intercept, slope = _linear_regression(train)
    baseline_errors = [float(row.forecast_value) - float(row.observation_value) for row in test]
    corrected_errors = [
        intercept + slope * float(row.forecast_value) - float(row.observation_value)
        for row in test
    ]
    baseline = _metrics(baseline_errors)
    corrected = _metrics(corrected_errors)
    selected = corrected[0] < baseline[0]
    return TemperatureCorrection(
        variable="temperature_2m",
        model="linear_regression" if selected else None,
        selected=selected,
        intercept=intercept if selected else 0.0,
        slope=slope if selected else 1.0,
        train_count=len(train),
        test_count=len(test),
        baseline_mae=baseline[0],
        corrected_mae=corrected[0],
        baseline_rmse=baseline[1],
        corrected_rmse=corrected[1],
        baseline_bias=baseline[2],
        corrected_bias=corrected[2],
    )


def _baseline(train_count: int, test_count: int) -> TemperatureCorrection:
    return TemperatureCorrection("temperature_2m", None, False, 0.0, 1.0, train_count, test_count, None, None, None, None, None, None)


def _linear_regression(samples: list[EvaluationSample]) -> tuple[float, float]:
    values = [(float(row.forecast_value), float(row.observation_value)) for row in samples]
    count = len(values)
    x_mean = fsum(value[0] for value in values) / count
    y_mean = fsum(value[1] for value in values) / count
    denominator = fsum((x - x_mean) ** 2 for x, _ in values)
    if denominator == 0:
        return y_mean - x_mean, 1.0
    slope = fsum((x - x_mean) * (y - y_mean) for x, y in values) / denominator
    return y_mean - slope * x_mean, slope


def _metrics(errors: list[float]) -> tuple[float, float, float]:
    count = len(errors)
    return (
        fsum(abs(error) for error in errors) / count,
        sqrt(fsum(error * error for error in errors) / count),
        fsum(errors) / count,
    )


def _is_finite(value: float | None) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _utc_timestamp(value) -> float:
    return value.timestamp() if value.tzinfo is not None else value.replace(tzinfo=__import__("datetime").timezone.utc).timestamp()
