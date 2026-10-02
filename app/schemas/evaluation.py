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
