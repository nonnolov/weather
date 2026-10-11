"""Append a rain-only flood-watch note; never make an independent send decision."""
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import ForecastRun, HourlyForecast
from app.models.location import Location
from app.services.rainfall_flood_assessment import build_rainfall_flood_assessment

FLOOD_WATCH_TEXT = (
    "⚠️ พยากรณ์ฝนบริเวณนี้เข้าเกณฑ์เฝ้าระวังน้ำท่วมจากฝน "
    "ควรติดตามสถานการณ์ โดยเฉพาะจุดระบายน้ำช้า "
    "(เป็นการคัดกรองจากฝน ไม่ยืนยันว่าจะเกิดน้ำท่วม)"
)


def flood_enrichment(run, hourly, location, *, now: datetime) -> dict:
    # Explicit supplied rows prevent lazy ORM loading or switching to a newer run.
    snapshot = SimpleNamespace(id=run.id, location_id=run.location_id,
                               provider=run.provider, retrieved_at=run.retrieved_at,
                               hourly_forecasts=hourly)
    report = build_rainfall_flood_assessment(snapshot, now=now, location=location)
    return {key: report[key] for key in (
        "location_id", "forecast_run_id", "retrieved_at", "assessment_status",
        "risk_detected", "risk_level", "assessment_reason_codes",
        "screening_rule_version", "screening_source_url", "assessment_basis",
        "historical_validation_status", "trigger_windows", "limitations",
    )}


async def read_flood_snapshot(db: AsyncSession, source_id: int, location_id: int):
    run = (await db.execute(select(
        ForecastRun.id, ForecastRun.location_id, ForecastRun.provider, ForecastRun.retrieved_at,
    ).where(ForecastRun.id == source_id, ForecastRun.location_id == location_id)
      .with_for_update(read=True))).first()
    location = await db.scalar(select(Location).where(
        Location.id == location_id, Location.is_active.is_(True)).with_for_update(read=True))
    if run is None or location is None:
        return None
    hourly = (await db.execute(select(
        HourlyForecast.valid_time, HourlyForecast.precipitation,
    ).where(HourlyForecast.forecast_run_id == source_id)
      .order_by(HourlyForecast.valid_time).with_for_update(read=True))).all()
    return run, hourly, location


def enrich_rain_message(message: str, evidence: dict | None, *,
                        source_id: int, location_id: int) -> str:
    positive = (
        isinstance(evidence, dict)
        and evidence.get("risk_detected") is True
        and evidence.get("assessment_status") == "rainfall_flood_potential"
        and evidence.get("risk_level") == "watch"
        and evidence.get("forecast_run_id") == source_id
        and evidence.get("location_id") == location_id
        and bool(evidence.get("trigger_windows"))
    )
    result = message + "\n\n" + FLOOD_WATCH_TEXT if positive else message
    if len(result) > 5000:
        raise ValueError("Rain message exceeds LINE text limit")
    return result
