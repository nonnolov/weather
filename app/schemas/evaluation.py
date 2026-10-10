from datetime import datetime

from pydantic import BaseModel


class ForecastMetricRead(BaseModel):
    variable: str
    horizon_hours: float
    sample_count: int
    mae: float
    rmse: float
    bias: float

    model_config = {"from_attributes": True}


class ForecastEvaluationRead(BaseModel):
    location_id: int
    metrics: list[ForecastMetricRead]


class BiasCorrectionValueRead(BaseModel):
    valid_time: datetime
    variable: str
    horizon_hours: float
    baseline_value: float
    corrected_value: float
    model: str | None
    applied: bool

    model_config = {"from_attributes": True}


class BiasCorrectionEvaluationRead(BaseModel):
    variable: str
    model: str | None
    selected: bool
    train_count: int
    test_count: int
    baseline_mae: float | None
    corrected_mae: float | None
    baseline_rmse: float | None
    corrected_rmse: float | None
    baseline_bias: float | None
    corrected_bias: float | None

    model_config = {"from_attributes": True}


class CorrectedForecastRead(BaseModel):
    forecast_run_id: int
    location_id: int
    values: list[BiasCorrectionValueRead]
    evaluations: list[BiasCorrectionEvaluationRead]


class PrecipitationOccurrenceRead(BaseModel):
    event_threshold_mm: float
    hits: int
    misses: int
    false_alarms: int
    correct_dry: int
    precision: float | None
    recall: float | None
    false_alarm_ratio: float | None
    brier_sample_count: int
    brier_score: float | None


class AuditedMetricRead(BaseModel):
    provider: str
    reference_source: str
    reference_kind: str
    variable: str
    unit: str
    horizon_start_hours: int
    horizon_end_hours: int
    horizon_basis: str
    sample_count: int
    unique_target_count: int
    mae: float
    rmse: float
    bias: float
    precipitation_occurrence: PrecipitationOccurrenceRead | None


class ForecastAuditRead(BaseModel):
    audit_version: str
    location_id: int
    since: datetime
    as_of: datetime
    status: str
    accuracy_claim_available: bool
    verified_at_point_pairs: int
    alert_delivery_evaluated: bool
    selection_policy: str
    horizon_basis: str
    candidate_pairs: int
    matched_pairs: int
    eligible_pairs: int
    selected_pairs: int
    excluded_by_reason: dict[str, int]
    reference_sources: dict[str, int]
    metrics: list[AuditedMetricRead]
