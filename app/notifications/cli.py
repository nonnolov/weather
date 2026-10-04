"""CLI for sending deduplicated forecast alerts to LINE."""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.forecast import ForecastRun
from app.models.location import Location
from app.notifications.service import (
    configured_recipient_ids,
    send_forecast_alert,
)
from app.notifications.line_client import LineClient
from app.notifications.rain_alerts import refresh_and_send_rain_alerts


async def send_seed_alerts() -> dict[str, int]:
    token = settings.LINE_CHANNEL_ACCESS_TOKEN
    recipients = configured_recipient_ids()
    if not token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is not configured")
    if not recipients:
        raise RuntimeError("LINE_USER_IDS is not configured")

    client = LineClient(token, settings.LINE_API_BASE_URL)
    counts: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        seed_slugs = ("chon-buri-city", "pattaya", "si-racha", "bang-lamung")
        locations = await db.scalars(
            select(Location).where(Location.slug.in_(seed_slugs), Location.is_active.is_(True))
        )
        for location in locations:
            run = await db.scalar(
                select(ForecastRun)
                .where(ForecastRun.location_id == location.id)
                .order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc())
                .limit(1)
            )
            sent = 0
            if run is not None:
                for recipient in recipients:
                    if await send_forecast_alert(db, run, recipient, client):
                        sent += 1
            counts[location.slug] = sent
        await db.commit()
    return counts


async def send_user_alerts() -> dict[str, int]:
    token = settings.LINE_CHANNEL_ACCESS_TOKEN
    if not token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is not configured")
    client = LineClient(token, settings.LINE_API_BASE_URL)
    async with AsyncSessionLocal() as db:
        return await refresh_and_send_rain_alerts(db, client)


async def _main() -> None:
    counts = await send_user_alerts()
    print(f"{counts['sent']} sent, {counts['skipped']} skipped")


if __name__ == "__main__":
    asyncio.run(_main())
