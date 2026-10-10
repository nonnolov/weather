from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.location import Location
from app.services.air_quality import AirQualityService, get_air_quality_service

router = APIRouter()

@router.get("/air-quality/{location_id}", tags=["air-quality"])
async def air_quality(location_id: int, db: AsyncSession = Depends(get_db),
                      service: AirQualityService = Depends(get_air_quality_service)):
    location = await db.get(Location, location_id)
    if location is None or not location.is_active:
        raise HTTPException(status_code=404, detail="Active location not found.")
    report = await service.get(location.latitude, location.longitude)
    return {"location_id": location.id, "timezone": location.timezone, **report}
