from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.forecast import DailyForecast, ForecastRun
from app.models.notification import NotificationDelivery
from app.models.location import Location
from app.models.user import User
from app.notifications.formatter import format_forecast_alert
from app.notifications.line_client import LineClient


class NotificationError(RuntimeError):
    pass


def configured_recipient_ids() -> list[str]:
    return [item.strip() for item in settings.LINE_USER_IDS.split(",") if item.strip()]


async def _lock_dedupe_key(db: AsyncSession, dedupe_key: str, recipient_id: str) -> None:
    """Serialize concurrent sends for the same recipient and dedupe key on PostgreSQL."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        lock_key = f"line:{recipient_id}:{dedupe_key}"
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_key))))


async def send_forecast_alert(
    db: AsyncSession,
    run: ForecastRun,
    recipient_id: str,
    client: LineClient,
    alert_kind: str = "7day",
) -> bool:
    """Send one deduplicated forecast alert. Return True when sent."""
    dedupe_key = f"forecast:{run.location_id}:{run.retrieved_at.date()}:{alert_kind}"
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

    daily_rows = list(
        (
            await db.scalars(
                select(DailyForecast)
                .where(DailyForecast.forecast_run_id == run.id)
                .order_by(DailyForecast.forecast_date)
            )
        ).all()
    )
    location_name = await db.scalar(select(Location.name).where(Location.id == run.location_id))
    await client.push_text(
        recipient_id,
        format_forecast_alert(run, daily_rows, location_name=location_name),
    )
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


async def send_current_location_alerts(db: AsyncSession, client: LineClient) -> dict[str, int]:
    users = list((await db.scalars(select(User).where(User.current_location_id.is_not(None)))).all())
    sent = 0
    skipped = 0
    for user in users:
        run = await db.scalar(select(ForecastRun).where(ForecastRun.location_id == user.current_location_id).order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc()).limit(1))
        if run is None:
            skipped += 1
            continue
        if await send_forecast_alert(db, run, user.external_id, client):
            sent += 1
        else:
            skipped += 1
    return {"sent": sent, "skipped": skipped}
