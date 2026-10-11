"""Read-only provider request reservations: python -m app.ingestion.quota_status."""
import asyncio
import json
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.forecast_fetch import ProviderRequestBudget
from app.core.config import settings


async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(ProviderRequestBudget).order_by(
            ProviderRequestBudget.provider, ProviderRequestBudget.period))).all()
        print(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(),
            "sharing_enabled": settings.FORECAST_SHARING_ENABLED,
            "google_live_preview_enabled": settings.GOOGLE_WEATHER_PREVIEW_ENABLED,
            "google_production_eligible": False,
            "google_monthly_limit": settings.GOOGLE_WEATHER_MONTHLY_LIMIT,
            "google_daily_limit": settings.GOOGLE_WEATHER_DAILY_LIMIT,
            "reservation_upper_bounds": [{"provider": r.provider, "period": r.period, "reserved": r.reserved} for r in rows],
            "scope": "this application only; other billing-account applications not counted"}))


if __name__ == "__main__":
    asyncio.run(main())
