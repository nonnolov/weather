from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.models.user import User
from app.notifications.formatter import format_rain_alert
from app.notifications.line_client import LineClient
from app.notifications.rain_risk import find_daily_peak_period, find_rain_risk_periods
from app.notifications.service import _lock_dedupe_key


async def send_rain_alert(
    db: AsyncSession,
    run: ForecastRun,
    recipient_id: str,
    client: LineClient,
) -> bool:
    """Send one deduplicated rain-risk alert when a qualifying period exists."""
    location = await db.scalar(select(Location).where(Location.id == run.location_id))
    if location is None:
        return False

    try:
        tz = ZoneInfo(location.timezone)
    except Exception:
        tz = ZoneInfo("Asia/Bangkok")
    alert_date = datetime.now(tz).date()

    hourly = list(
        (
            await db.scalars(
                select(HourlyForecast)
                .where(HourlyForecast.forecast_run_id == run.id)
                .order_by(HourlyForecast.valid_time)
            )
        ).all()
    )
    periods = find_rain_risk_periods(hourly, target_date=alert_date)
    daily_peak = False
    if not periods:
        peak = find_daily_peak_period(hourly, target_date=alert_date)
        if peak is None:
            return False
        periods = [peak]
        daily_peak = True

    dedupe_key = f"rain:{run.location_id}:{alert_date.isoformat()}"
    await _lock_dedupe_key(db, dedupe_key, recipient_id)
    existing = await db.scalar(
        select(NotificationDelivery.id).where(
            NotificationDelivery.channel == "line",
            NotificationDelivery.recipient_id == recipient_id,
            NotificationDelivery.dedupe_key == dedupe_key,
        )
    )
    if existing is not None:
        return False

    run.location = location
    message = format_rain_alert(
        run,
        periods,
        alert_date=alert_date,
        location_name=_location_display_name(location),
        daily_peak=daily_peak,
    )
    await client.push_text(recipient_id, message)
    db.add(
        NotificationDelivery(
            location_id=run.location_id,
            channel="line",
            recipient_id=recipient_id,
            dedupe_key=dedupe_key,
        )
    )
    await db.flush()
    return True


async def refresh_and_send_rain_alerts(db: AsyncSession, client: LineClient) -> dict[str, int]:
    """Refresh each active user location once, then send qualifying rain alerts."""
    from app.ingestion.service import IngestionError, ingest_forecast_for_location

    location_ids = list(
        (
            await db.scalars(
                select(User.current_location_id)
                .where(User.current_location_id.is_not(None))
                .distinct()
            )
        ).all()
    )
    refreshed = 0
    refresh_failed = 0

    for location_id in location_ids:
        location = await db.scalar(select(Location).where(Location.id == location_id))
        if location is None:
            refresh_failed += 1
            continue
        try:
            await ingest_forecast_for_location(db, location, forecast_days=7)
            await db.commit()
            refreshed += 1
        except IngestionError:
            await db.rollback()
            refresh_failed += 1

    counts = await send_current_rain_alerts(db, client)
    await db.commit()
    counts["refreshed"] = refreshed
    counts["refresh_failed"] = refresh_failed
    return counts


async def send_current_rain_alerts(db: AsyncSession, client: LineClient) -> dict[str, int]:
    users = list(
        (
            await db.scalars(
                select(User).where(User.current_location_id.is_not(None))
            )
        ).all()
    )
    sent = 0
    skipped = 0
    for user in users:
        run = await db.scalar(
            select(ForecastRun)
            .where(ForecastRun.location_id == user.current_location_id)
            .order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc())
            .limit(1)
        )
        if run is None:
            skipped += 1
            continue
        if await send_rain_alert(db, run, user.external_id, client):
            sent += 1
        else:
            skipped += 1
    return {"sent": sent, "skipped": skipped}


def _location_display_name(location: Location) -> str:
    parts = []
    if location.subdistrict:
        parts.append(f"ต.{location.subdistrict}")
    if location.district:
        parts.append(f"อ.{location.district}")
    if location.province:
        parts.append(f"จ.{location.province}")
    return " ".join(parts) if parts else location.name
