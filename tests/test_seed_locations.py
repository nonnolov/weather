"""
Tests for the Chon Buri seed location data and seed_locations() function.

All tests run against the in-memory SQLite database — no PostgreSQL required.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.seeds.locations import CHON_BURI_LOCATIONS, LocationSeed, seed_locations
from app.models.location import Location


# ── Data integrity tests (no DB needed) ────────────────────────────────────────────

def test_seed_has_four_locations() -> None:
    assert len(CHON_BURI_LOCATIONS) == 4


def test_seed_slugs_are_unique() -> None:
    slugs = [loc.slug for loc in CHON_BURI_LOCATIONS]
    assert len(slugs) == len(set(slugs)), "Duplicate slugs in seed data"


def test_seed_slugs_match_expected() -> None:
    slugs = {loc.slug for loc in CHON_BURI_LOCATIONS}
    assert slugs == {"chon-buri-city", "pattaya", "si-racha", "bang-lamung"}


def test_seed_names_match_expected() -> None:
    names = {loc.name for loc in CHON_BURI_LOCATIONS}
    assert names == {"Chon Buri City", "Pattaya", "Si Racha", "Bang Lamung"}


def test_all_locations_use_bangkok_timezone() -> None:
    for loc in CHON_BURI_LOCATIONS:
        assert loc.timezone == "Asia/Bangkok", (
            f"{loc.slug} has timezone {loc.timezone!r}, expected 'Asia/Bangkok'"
        )


def test_all_locations_use_thailand_country_code() -> None:
    for loc in CHON_BURI_LOCATIONS:
        assert loc.country_code == "TH", (
            f"{loc.slug} has country_code {loc.country_code!r}, expected 'TH'"
        )


def test_all_locations_use_open_meteo_provider() -> None:
    for loc in CHON_BURI_LOCATIONS:
        assert loc.provider == "open_meteo"


def test_all_locations_are_active() -> None:
    for loc in CHON_BURI_LOCATIONS:
        assert loc.is_active is True


@pytest.mark.parametrize("loc", CHON_BURI_LOCATIONS)
def test_coordinates_are_in_valid_range(loc: LocationSeed) -> None:
    assert -90.0 <= loc.latitude <= 90.0, f"{loc.slug}: latitude out of range"
    assert -180.0 <= loc.longitude <= 180.0, f"{loc.slug}: longitude out of range"


@pytest.mark.parametrize("loc", CHON_BURI_LOCATIONS)
def test_coordinates_are_in_chon_buri_region(loc: LocationSeed) -> None:
    """Sanity-check: all locations should be in the Chon Buri coastal region."""
    assert 12.5 <= loc.latitude <= 14.0, (
        f"{loc.slug}: latitude {loc.latitude} outside expected Chon Buri range"
    )
    assert 100.5 <= loc.longitude <= 101.5, (
        f"{loc.slug}: longitude {loc.longitude} outside expected Chon Buri range"
    )


@pytest.mark.parametrize("loc", CHON_BURI_LOCATIONS)
def test_slug_format(loc: LocationSeed) -> None:
    """Slugs must match the schema pattern: lowercase letters, digits, hyphens only."""
    import re
    assert re.match(r"^[a-z0-9-]+$", loc.slug), (
        f"{loc.slug!r} does not match slug pattern"
    )


# ── Functional tests (use in-memory SQLite via conftest fixtures) ─────────────────

@pytest.mark.asyncio
async def test_seed_creates_all_four_locations(db_session: AsyncSession) -> None:
    results = await seed_locations(db_session)
    assert len(results) == 4
    assert all(status == "created" for status in results.values())


@pytest.mark.asyncio
async def test_seed_locations_are_persisted(db_session: AsyncSession) -> None:
    await seed_locations(db_session)
    result = await db_session.execute(
        select(Location).where(Location.country_code == "TH")
    )
    rows = result.scalars().all()
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    """Running seed twice must not create duplicates."""
    first = await seed_locations(db_session)
    second = await seed_locations(db_session)

    assert all(s == "created" for s in first.values())
    assert all(s == "skipped" for s in second.values())

    result = await db_session.execute(
        select(Location).where(Location.country_code == "TH")
    )
    rows = result.scalars().all()
    assert len(rows) == 4  # still exactly 4, no duplicates


@pytest.mark.asyncio
async def test_seed_location_fields(db_session: AsyncSession) -> None:
    """Spot-check persisted field values for Chon Buri City."""
    await seed_locations(db_session)
    result = await db_session.execute(
        select(Location).where(Location.slug == "chon-buri-city")
    )
    loc = result.scalar_one()
    assert loc.name == "Chon Buri City"
    assert loc.timezone == "Asia/Bangkok"
    assert loc.country_code == "TH"
    assert loc.provider == "open_meteo"
    assert loc.is_active is True
    assert abs(loc.latitude - 13.3611) < 0.001
    assert abs(loc.longitude - 100.9847) < 0.001


@pytest.mark.asyncio
async def test_seed_partial_existing_skips_correctly(db_session: AsyncSession) -> None:
    """If some locations already exist, only the missing ones are created."""
    # Pre-insert Pattaya manually
    from datetime import datetime, timezone as tz
    existing = Location(
        name="Pattaya",
        slug="pattaya",
        latitude=12.9236,
        longitude=100.8825,
        timezone="Asia/Bangkok",
        country_code="TH",
        provider="open_meteo",
        created_at=datetime.now(tz.utc),
        updated_at=datetime.now(tz.utc),
    )
    db_session.add(existing)
    await db_session.flush()

    results = await seed_locations(db_session)
    assert results["pattaya"] == "skipped"
    assert results["chon-buri-city"] == "created"
    assert results["si-racha"] == "created"
    assert results["bang-lamung"] == "created"
