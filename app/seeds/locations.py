"""
Seed script — initial Chon Buri forecast locations.

Usage (requires a running PostgreSQL instance):
    python -m app.seeds.locations

Idempotent: locations are matched by slug; existing rows are left unchanged.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.location import Location


@dataclass(frozen=True)
class LocationSeed:
    """Plain-data representation of a seed location."""
    name: str
    slug: str
    latitude: float
    longitude: float
    timezone: str
    country_code: str
    description: str
    provider: str = "open_meteo"
    is_active: bool = True


# ── Seed data ────────────────────────────────────────────────────────────────────

CHON_BURI_LOCATIONS: list[LocationSeed] = [
    LocationSeed(
        name="Chon Buri City",
        slug="chon-buri-city",
        latitude=13.3611,
        longitude=100.9847,
        timezone="Asia/Bangkok",
        country_code="TH",
        description="Provincial capital of Chon Buri, eastern Gulf coast of Thailand.",
    ),
    LocationSeed(
        name="Pattaya",
        slug="pattaya",
        latitude=12.9236,
        longitude=100.8825,
        timezone="Asia/Bangkok",
        country_code="TH",
        description="Coastal resort city in Chon Buri province.",
    ),
    LocationSeed(
        name="Si Racha",
        slug="si-racha",
        latitude=13.1736,
        longitude=100.9170,
        timezone="Asia/Bangkok",
        country_code="TH",
        description="Industrial and port city in Chon Buri province.",
    ),
    LocationSeed(
        name="Bang Lamung",
        slug="bang-lamung",
        latitude=12.9500,
        longitude=100.8833,
        timezone="Asia/Bangkok",
        country_code="TH",
        description="District in Chon Buri province, encompassing the Pattaya area.",
    ),
]


# ── Seed function ──────────────────────────────────────────────────────────────────

async def seed_locations(
    session: AsyncSession,
    locations: list[LocationSeed] = CHON_BURI_LOCATIONS,
) -> dict[str, str]:
    """
    Insert seed locations that do not already exist (matched by slug).
    Returns a dict mapping slug → 'created' | 'skipped'.
    """
    results: dict[str, str] = {}
    now = datetime.now(timezone.utc)

    for seed in locations:
        existing = await session.execute(
            select(Location).where(Location.slug == seed.slug)
        )
        if existing.scalar_one_or_none() is not None:
            results[seed.slug] = "skipped"
            continue

        location = Location(
            name=seed.name,
            slug=seed.slug,
            latitude=seed.latitude,
            longitude=seed.longitude,
            timezone=seed.timezone,
            country_code=seed.country_code,
            description=seed.description,
            provider=seed.provider,
            is_active=seed.is_active,
            created_at=now,
            updated_at=now,
        )
        session.add(location)
        results[seed.slug] = "created"

    await session.flush()
    return results


# ── CLI entry point ──────────────────────────────────────────────────────────────────

async def _main() -> None:
    async with AsyncSessionLocal() as session:
        results = await seed_locations(session)
        await session.commit()

    for slug, status in results.items():
        print(f"  {status:>7}  {slug}")
    created = sum(1 for s in results.values() if s == "created")
    skipped = sum(1 for s in results.values() if s == "skipped")
    print(f"\nDone: {created} created, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(_main())
