"""Public totals; visitor input cannot directly supply a location total."""
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, UUID4
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.audience import audience_counts, record_member
from app.services.rate_limit import audience_visit_rate_limit

router = APIRouter(prefix="/audience", tags=["audience"])

class VisitorRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor_id: UUID4

class AudienceCounts(BaseModel):
    received_locations: int
    website_visitors: int

@router.get("", response_model=AudienceCounts)
async def get_audience(response: Response, db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await audience_counts(db)

@router.post(
    "/visit",
    response_model=AudienceCounts,
    dependencies=[Depends(audience_visit_rate_limit)],
)
async def register_visit(payload: VisitorRegistration, response: Response, db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    await record_member(db, "browser", str(payload.visitor_id))
    return await audience_counts(db)
