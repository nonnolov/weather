from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.location import Location
from app.models.forecast import ForecastRun, HourlyForecast, DailyForecast
from app.schemas.forecast import ForecastRunRead, ForecastRunDetail, IngestResponse
from app.ingestion.service import ingest_forecast_for_location, IngestionError

router = APIRouter()


@router.post(
    "/ingest/{location_id}",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["ingestion"],
)
async def trigger_ingestion(
    location_id: int,
    forecast_days: int = Query(default=7, ge=1, le=16),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Trigger a fresh forecast ingestion for a location."""
    location = await _get_location_or_404(db, location_id)

    try:
        run = await ingest_forecast_for_location(db, location, forecast_days=forecast_days)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Count persisted records
    hourly_count_result = await db.execute(
        select(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id)
    )
    daily_count_result = await db.execute(
        select(DailyForecast).where(DailyForecast.forecast_run_id == run.id)
    )
    hourly_records = len(hourly_count_result.scalars().all())
    daily_records = len(daily_count_result.scalars().all())

    return IngestResponse(
        forecast_run_id=run.id,
        location_id=location_id,
        provider=run.provider,
        hourly_records=hourly_records,
        daily_records=daily_records,
        retrieved_at=run.retrieved_at,
    )


@router.get(
    "/forecast/{location_id}",
    response_model=ForecastRunDetail,
    tags=["forecasts"],
)
async def get_latest_forecast(
    location_id: int,
    db: AsyncSession = Depends(get_db),
) -> ForecastRunDetail:
    """
    Return the most recent forecast run for a location,
    including all hourly and daily records.
    """
    await _get_location_or_404(db, location_id)

    result = await db.execute(
        select(ForecastRun)
        .where(ForecastRun.location_id == location_id)
        .options(
            selectinload(ForecastRun.hourly_forecasts),
            selectinload(ForecastRun.daily_forecasts),
        )
        .order_by(ForecastRun.retrieved_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No forecast runs found for location {location_id}.",
        )

    return ForecastRunDetail(
        id=run.id,
        location_id=run.location_id,
        provider=run.provider,
        retrieved_at=run.retrieved_at,
        model_run_time=run.model_run_time,
        forecast_days=run.forecast_days,
        hourly=run.hourly_forecasts,
        daily=run.daily_forecasts,
    )


@router.get(
    "/forecast/{location_id}/runs",
    response_model=list[ForecastRunRead],
    tags=["forecasts"],
)
async def list_forecast_runs(
    location_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[ForecastRun]:
    """List historical forecast runs for a location (newest first)."""
    await _get_location_or_404(db, location_id)

    result = await db.execute(
        select(ForecastRun)
        .where(ForecastRun.location_id == location_id)
        .order_by(ForecastRun.retrieved_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _get_location_or_404(db: AsyncSession, location_id: int) -> Location:
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found.",
        )
    return location
