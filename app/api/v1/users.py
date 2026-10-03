import hashlib
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.forecast import DailyForecast, ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.user import User
from app.schemas.forecast import ForecastRunDetail, IngestResponse
from app.schemas.location import LocationFromGps
from app.schemas.user import UserLocationRead
from app.ingestion.service import IngestionError, ingest_forecast_for_location
from app.services.geocoding import (
    AdministrativeArea,
    ReverseGeocoder,
    ReverseGeocodingError,
    get_reverse_geocoder,
)


router = APIRouter()


@router.post(
    "/{external_user_id}/location/from-gps",
    response_model=UserLocationRead,
    status_code=status.HTTP_200_OK,
)
async def set_user_location_from_gps(
    payload: LocationFromGps,
    external_user_id: str = Path(min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
    geocoder: ReverseGeocoder = Depends(get_reverse_geocoder),
) -> UserLocationRead:
    """Resolve GPS coordinates and set an external user's current location."""
    try:
        area = await geocoder.reverse(payload.latitude, payload.longitude)
    except ReverseGeocodingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    name, slug = _gps_location_identity(payload.latitude, payload.longitude, area)
    result = await db.execute(select(Location).where(Location.slug == slug))
    location = result.scalar_one_or_none()
    if location is None:
        location = Location(
            name=name,
            slug=slug,
            latitude=payload.latitude,
            longitude=payload.longitude,
            province=area.province,
            district=area.district,
            subdistrict=area.subdistrict,
            country_code=area.country_code.upper() if area.country_code else None,
        )
        db.add(location)
        await db.flush()

    result = await db.execute(select(User).where(User.external_id == external_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(external_id=external_user_id, current_location=location)
        db.add(user)
    else:
        user.current_location = location
    await db.flush()
    await db.refresh(location)
    return UserLocationRead(external_user_id=user.external_id, location=location)


@router.get(
    "/{external_user_id}/forecast",
    response_model=ForecastRunDetail,
    status_code=status.HTTP_200_OK,
)
async def get_user_forecast(
    external_user_id: str = Path(min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
) -> ForecastRunDetail:
    """Return the latest stored forecast for the user's current GPS location."""
    location = await _get_user_current_location(db, external_user_id)
    result = await db.execute(
        select(ForecastRun)
        .where(ForecastRun.location_id == location.id)
        .options(
            selectinload(ForecastRun.hourly_forecasts),
            selectinload(ForecastRun.daily_forecasts),
        )
        .order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No forecast runs found for user {external_user_id}.",
        )
    return _forecast_run_detail(run)


@router.post(
    "/{external_user_id}/forecast/refresh",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def refresh_user_forecast(
    external_user_id: str = Path(min_length=1, max_length=255),
    forecast_days: int = Query(default=7, ge=1, le=16),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingest a fresh forecast using the user's current location coordinates."""
    location = await _get_user_current_location(db, external_user_id)
    try:
        run = await ingest_forecast_for_location(db, location, forecast_days=forecast_days)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    hourly_count = await db.execute(select(HourlyForecast).where(HourlyForecast.forecast_run_id == run.id))
    daily_count = await db.execute(select(DailyForecast).where(DailyForecast.forecast_run_id == run.id))
    return IngestResponse(
        forecast_run_id=run.id,
        location_id=location.id,
        provider=run.provider,
        hourly_records=len(hourly_count.scalars().all()),
        daily_records=len(daily_count.scalars().all()),
        retrieved_at=run.retrieved_at,
    )


async def _get_user_current_location(db: AsyncSession, external_user_id: str) -> Location:
    result = await db.execute(
        select(User).where(User.external_id == external_user_id).options(selectinload(User.current_location))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {external_user_id} not found.")
    if user.current_location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {external_user_id} has no current location.")
    return user.current_location


def _forecast_run_detail(run: ForecastRun) -> ForecastRunDetail:
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


def _gps_location_identity(
    latitude: float,
    longitude: float,
    area: AdministrativeArea,
) -> tuple[str, str]:
    """Match existing GPS-location identity format for cross-endpoint reuse."""
    coordinates = f"{latitude:.6f}, {longitude:.6f}"
    name = f"{area.subdistrict}, {area.district}, {area.province} ({coordinates})"
    digest_source = f"{area.province}|{area.district}|{area.subdistrict}|{latitude!r}|{longitude!r}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    ascii_area = unicodedata.normalize(
        "NFKD", "-".join((area.subdistrict, area.district, area.province))
    )
    ascii_area = ascii_area.encode("ascii", "ignore").decode("ascii").lower()
    slug_base = re.sub(r"[^a-z0-9]+", "-", ascii_area).strip("-") or "gps-location"
    return name[:255], f"{slug_base[:87].rstrip('-')}-{digest}"
