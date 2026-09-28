from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.location import Location
from app.schemas.location import LocationCreate, LocationRead, LocationUpdate

router = APIRouter()


@router.get("", response_model=list[LocationRead])
async def list_locations(db: AsyncSession = Depends(get_db)) -> list[Location]:
    """Return all locations."""
    result = await db.execute(select(Location).order_by(Location.id))
    return list(result.scalars().all())


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
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


@router.get("/{location_id}", response_model=LocationRead)
async def get_location(
    location_id: int,
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Return a single location by ID."""
    location = await _get_or_404(db, location_id)
    return location


@router.patch("/{location_id}", response_model=LocationRead)
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


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a location and all its associated data."""
    location = await _get_or_404(db, location_id)
    await db.delete(location)


async def _get_or_404(db: AsyncSession, location_id: int) -> Location:
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found.",
        )
    return location
