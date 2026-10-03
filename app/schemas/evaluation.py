from datetime import datetime

from pydantic import BaseModel


class ForecastMetricRead(BaseModel):
    variable: str
    horizon_hours: float
    sample_count: int
    mae: float
    rmse: float
    bias: float


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
