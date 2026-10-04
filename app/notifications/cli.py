"""CLI for sending deduplicated forecast alerts to LINE."""
from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.ingestion.service import ingest_seed_observations
from app.notifications.line_client import LineClient
from app.notifications.rain_alerts import refresh_and_send_rain_alerts


async def send_user_alerts():
    token = settings.LINE_CHANNEL_ACCESS_TOKEN
    if not token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is not configured")
    client = LineClient(token, settings.LINE_API_BASE_URL)
    async with AsyncSessionLocal() as db:
        return await refresh_and_send_rain_alerts(db, client)


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        observation_counts = await ingest_seed_observations(db)
        await db.commit()
    print(f"Observation ingestion: {sum(observation_counts.values())} created")
    counts = await send_user_alerts()
    print(f"{counts['sent']} sent, {counts['skipped']} skipped")


if __name__ == "__main__":
    asyncio.run(_main())
