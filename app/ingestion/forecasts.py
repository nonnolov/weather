"""Idempotent initial forecast ingestion for active seed locations."""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.ingestion.service import ingest_forecast_for_location
from app.models.forecast import ForecastRun
from app.models.location import Location


async def ingest_missing_forecasts() -> int:
    async with AsyncSessionLocal() as db:
        locations = (
            await db.execute(
                select(Location).where(Location.is_active.is_(True)).order_by(Location.id)
            )
        ).scalars().all()
        created = 0
        for location in locations:
            exists = await db.scalar(
                select(ForecastRun.id)
                .where(ForecastRun.location_id == location.id)
                .limit(1)
            )
            if exists is not None:
                continue
            await ingest_forecast_for_location(db, location)
            created += 1
        await db.commit()
        return created


if __name__ == "__main__":
    print(f"Initial forecast ingestion: {asyncio.run(ingest_missing_forecasts())} location(s) created")
