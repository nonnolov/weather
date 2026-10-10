"""Read-only public station collection status; no fetch or LINE side effects."""
from fastapi import APIRouter,Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.evaluation.rain_collection import station_status

router=APIRouter()

@router.get("/rain-reference/status")
async def read_station_status(db:AsyncSession=Depends(get_db)):
    return await station_status(db)
