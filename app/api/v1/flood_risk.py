from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.forecast import ForecastRun
from app.models.location import Location
from app.services.rainfall_flood_assessment import build_rainfall_flood_assessment

router = APIRouter()


@router.get("/flood-risk/{location_id}", tags=["flood-risk"])
async def rainfall_flood_risk(location_id: int, db: AsyncSession = Depends(get_db)):
    """Return forecast-rainfall exposure and source-backed rainfall screening with explicit limitations."""
    location = await db.get(Location, location_id)
    if location is None or not location.is_active:
        raise HTTPException(status_code=404, detail="Active location not found.")

    result = await db.execute(
        select(ForecastRun)
        .where(ForecastRun.location_id == location_id)
        .options(selectinload(ForecastRun.hourly_forecasts))
        .order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="No forecast is available for this location.")
    return {
        "timezone": location.timezone,
        **build_rainfall_flood_assessment(run, location=location),
    }
