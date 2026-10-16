from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.location import Location
from app.schemas.location import LocationCreate, LocationFromGps, LocationRead, LocationUpdate
from app.services.geocoding import (
    AdministrativeArea,
    ReverseGeocoder,
    ReverseGeocodingError,
    get_reverse_geocoder,
)
from app.services.maintenance_guard import require_nonproduction_maintenance
from app.services.rate_limit import admin_maintenance_rate_limit

router = APIRouter()


@router.get("", response_model=list[LocationRead])
async def list_locations(db: AsyncSession = Depends(get_db)) -> list[Location]:
    """Return all locations."""
    result = await db.execute(select(Location).order_by(Location.id))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(admin_maintenance_rate_limit),
        Depends(require_nonproduction_maintenance),
    ],
)
async def create_location(
    payload: LocationCreate,
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Create a new location."""
    # Check slug uniqueness
    existing = await db.execute(select(Location).where(Location.slug == payload.slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Location with slug {payload.slug!r} already exists.",
        )
    location = Location(**payload.model_dump())
    db.add(location)
    await db.flush()
    await db.refresh(location)
    return location


@router.post(
    "/from-gps",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(admin_maintenance_rate_limit),
        Depends(require_nonproduction_maintenance),
    ],
)
async def create_location_from_gps(
    payload: LocationFromGps,
    db: AsyncSession = Depends(get_db),
    geocoder: ReverseGeocoder = Depends(get_reverse_geocoder),
) -> Location:
    """Reverse-geocode GPS coordinates and create a location."""
    try:
        area = await geocoder.reverse(payload.latitude, payload.longitude)
    except ReverseGeocodingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    name, slug = _gps_location_identity(payload.latitude, payload.longitude, area)
    existing = await db.execute(select(Location).where(Location.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Location for these resolved coordinates already exists.",
        )
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
    await db.refresh(location)
    return location


@router.get("/{location_id}", response_model=LocationRead)
async def get_location(
    location_id: int,
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Return a single location by ID."""
    location = await _get_or_404(db, location_id)
    return location


@router.patch(
    "/{location_id}",
    response_model=LocationRead,
    dependencies=[
        Depends(admin_maintenance_rate_limit),
        Depends(require_nonproduction_maintenance),
    ],
)
async def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Partially update a location."""
    location = await _get_or_404(db, location_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, field, value)
    await db.flush()
    await db.refresh(location)
    return location


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(admin_maintenance_rate_limit),
        Depends(require_nonproduction_maintenance),
    ],
)
async def delete_location(
    location_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a location and all its associated data."""
    location = await _get_or_404(db, location_id)
    await db.delete(location)
    await db.flush()


async def _get_or_404(db: AsyncSession, location_id: int) -> Location:
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found.",
        )
    return location


def _gps_location_identity(
    latitude: float,
    longitude: float,
    area: AdministrativeArea,
) -> tuple[str, str]:
    coordinates = f"{latitude:.6f}, {longitude:.6f}"
    name = f"{area.subdistrict}, {area.district}, {area.province} ({coordinates})"
    digest_source = f"{area.province}|{area.district}|{area.subdistrict}|{latitude!r}|{longitude!r}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    ascii_area = unicodedata.normalize("NFKD", "-".join((area.subdistrict, area.district, area.province)))
    ascii_area = ascii_area.encode("ascii", "ignore").decode("ascii").lower()
    slug_base = re.sub(r"[^a-z0-9]+", "-", ascii_area).strip("-") or "gps-location"
    return name[:255], f"{slug_base[:87].rstrip('-')}-{digest}"
import hashlib
import re
import unicodedata
