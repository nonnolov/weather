"""Rain-risk period analysis for LINE alerts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

from app.models.forecast import HourlyForecast

PROBABILITY_THRESHOLD = 70.0
RAINFALL_THRESHOLD_MM = 10.0
DAILY_PEAK_PROBABILITY_THRESHOLD = 30.0
DAILY_PEAK_RAINFALL_THRESHOLD_MM = 5.0
MAX_RAIN_MM_FOR_SCORE = 30.0
TOP_PERIODS = 2


@dataclass(frozen=True)
class RainRiskPeriod:
    start: datetime
    end: datetime
    max_probability: float
    max_rainfall_mm: float
    duration_hours: int
    score: float


def _is_risky(row: HourlyForecast) -> bool:
    probability = row.precipitation_probability or 0.0
    rainfall = row.precipitation or 0.0
    return probability >= PROBABILITY_THRESHOLD or rainfall >= RAINFALL_THRESHOLD_MM


def _score(rows: Sequence[HourlyForecast]) -> float:
    max_probability = max((row.precipitation_probability or 0.0) for row in rows)
    max_rainfall = max((row.precipitation or 0.0) for row in rows)
    span_hours = int((rows[-1].valid_time - rows[0].valid_time).total_seconds() // 3600) + 1
    duration = min(span_hours, 4)

    probability_score = min(max_probability, 100.0) * 0.5
    intensity_score = min(max(max_rainfall, 0.0) / MAX_RAIN_MM_FOR_SCORE, 1.0) * 30.0
    duration_score = {1: 5.0, 2: 10.0, 3: 15.0, 4: 20.0}[duration]
    return probability_score + intensity_score + duration_score


def _local_date(row: HourlyForecast, timezone_name: str) -> date:
    value = row.valid_time
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(ZoneInfo(timezone_name)).date()


def find_rain_risk_periods(
    hourly_rows: Sequence[HourlyForecast],
    *,
    target_date,
    timezone_name: str = "UTC",
) -> list[RainRiskPeriod]:
    rows = sorted(
        (row for row in hourly_rows if _local_date(row, timezone_name) == target_date),
        key=lambda row: row.valid_time,
    )
    periods: list[list[HourlyForecast]] = []
    current: list[HourlyForecast] = []

    for row in rows:
        if not _is_risky(row):
            continue
        if current:
            gap_hours = (row.valid_time - current[-1].valid_time).total_seconds() / 3600
            if gap_hours > 2:
                periods.append(current)
                current = []
        current.append(row)

    if current:
        periods.append(current)

    result = []
    for period in periods:
        result.append(
            RainRiskPeriod(
                start=period[0].valid_time,
                end=period[-1].valid_time + timedelta(hours=1),
                max_probability=max(row.precipitation_probability or 0.0 for row in period),
                max_rainfall_mm=max(row.precipitation or 0.0 for row in period),
                duration_hours=len(period),
                score=_score(period),
            )
        )
    return sorted(result, key=lambda period: period.score, reverse=True)[:TOP_PERIODS]


def find_daily_peak_period(
    hourly_rows: Sequence[HourlyForecast],
    *,
    target_date,
    timezone_name: str = "UTC",
) -> RainRiskPeriod | None:
    """Return the single strongest fallback period when no risk alert qualifies."""
    rows = sorted(
        (row for row in hourly_rows if _local_date(row, timezone_name) == target_date),
        key=lambda row: row.valid_time,
    )
    candidates = [
        row
        for row in rows
        if (row.precipitation_probability or 0.0) >= DAILY_PEAK_PROBABILITY_THRESHOLD
        or (row.precipitation or 0.0) >= DAILY_PEAK_RAINFALL_THRESHOLD_MM
    ]
    if not candidates:
        return None

    row = max(candidates, key=lambda item: _score([item]))
    probability = row.precipitation_probability or 0.0
    rainfall = row.precipitation or 0.0
    return RainRiskPeriod(
        start=row.valid_time,
        end=row.valid_time + timedelta(hours=1),
        max_probability=probability,
        max_rainfall_mm=rainfall,
        duration_hours=1,
        score=_score([row]),
    )
