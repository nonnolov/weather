from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import DailyForecast, ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.models.user import User
from app.notifications.formatter import format_rain_alert
from app.notifications.flood_enrichment import flood_enrichment, enrich_rain_message
from app.notifications.line_client import LineApiError, LineClient
from app.notifications.rain_risk import (
    RainRiskPeriod,
    find_daily_peak_period,
    find_rain_risk_periods,
    rain_interval_local_date,
    rain_interval_start,
)
from app.notifications.service import _lock_dedupe_key
from app.notifications.rain_locking import lock_rain_scope


async def send_rain_alert(
    db: AsyncSession,
    run: ForecastRun,
    recipient_id: str,
    client: LineClient,
) -> bool:
    """Send one daily rain alert or below-threshold summary per recipient/location."""
    await lock_rain_scope(db, recipient_id, run.location_id)
    location = await db.scalar(select(Location).where(Location.id == run.location_id))
    if location is None:
        return False

    try:
        tz = ZoneInfo(location.timezone)
    except Exception:
        tz = ZoneInfo("Asia/Bangkok")
    alert_date = datetime.now(tz).date()
    retrieved = run.retrieved_at
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    if retrieved.astimezone(tz).date() != alert_date:
        return False  # Never present a stale forecast as today's fresh summary.

    hourly = list(
        (
            await db.scalars(
                select(HourlyForecast)
                .where(HourlyForecast.forecast_run_id == run.id)
                .order_by(HourlyForecast.valid_time)
            )
        ).all()
    )
    daily = list((await db.scalars(
        select(DailyForecast).where(
            DailyForecast.forecast_run_id == run.id,
            DailyForecast.forecast_date == alert_date,
        )
    )).all())
    today_hours = [
        row for row in hourly
        if rain_interval_local_date(row, tz.key) == alert_date
    ]
    if not any(
        row.precipitation is not None or row.precipitation_probability is not None
        for row in today_hours
    ):
        return False  # Missing data must not be described as below threshold.
    timezone_name = tz.key
    periods = find_rain_risk_periods(
        hourly,
        target_date=alert_date,
        timezone_name=timezone_name,
    )
    daily_peak = False
    if not periods:
        peak = find_daily_peak_period(
            hourly,
            target_date=alert_date,
            timezone_name=timezone_name,
        )
        if peak is not None:
            periods = [peak]
            daily_peak = True

    if not periods and (
        len(today_hours) < 24
        or any(row.precipitation is None or row.precipitation_probability is None for row in today_hours)
    ):
        return False  # Incomplete rain data cannot support a below-threshold claim.

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
        hourly_rows=hourly,
        daily_rows=daily,
    )
    flood = flood_enrichment(run, hourly, location, now=datetime.now(timezone.utc))
    message = enrich_rain_message(message, flood, source_id=run.id, location_id=run.location_id)
    # Freeze the exact formatter inputs before the network await. Never query
    # the latest run later, or retain references to mutable forecast objects.
    evidence = _rain_evidence(
        run, alert_date, timezone_name, periods, daily_peak, today_hours, daily, message
    )
    evidence["flood_screening"] = flood
    await client.push_text(recipient_id, message)
    db.add(
        NotificationDelivery(
            location_id=run.location_id,
            channel="line",
            recipient_id=recipient_id,
            dedupe_key=dedupe_key,
            forecast_run_id=run.id,
            rain_evidence=evidence,
        )
    )
    await db.flush()
    return True


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _rain_evidence(
    run: ForecastRun,
    alert_date: date,
    timezone_name: str,
    periods: list[RainRiskPeriod],
    daily_peak: bool,
    hours: list[HourlyForecast],
    daily: list[DailyForecast],
    message: str,
) -> dict:
    """Versioned, self-contained rain evidence; no recipient, GPS or raw metadata."""
    day = next((row for row in daily if row.forecast_date == alert_date), None)
    return {
        "schema_version": 1,
        "template_version": "rain-daily-periods-v3" if periods else "rain-daily-v1",
        "selection_version": "rain-selection-p0-02-v1",
        "mode": "daily_peak" if daily_peak else "strong_rain" if periods else "below_threshold_daily_summary",
        "alert_local_date": alert_date.isoformat(),
        "timezone": timezone_name,
        "source": {
            "forecast_run_id": run.id,
            "provider": run.provider,
            "retrieved_at": _utc_iso(run.retrieved_at),
            "model_run_time": _utc_iso(run.model_run_time),
        },
        # Preserve selection order (score-ranked), even though message windows
        # are sorted chronologically. Daily probability is never a period value.
        "selected_periods": [
            {
                "start": _utc_iso(period.start),
                "end": _utc_iso(period.end),
                "max_probability": period.max_probability,
                "max_rainfall_mm": period.max_rainfall_mm,
                "duration_hours": period.duration_hours,
                "score": period.score,
            }
            for period in periods
        ],
        "hourly_intervals": [
            {
                "start": _utc_iso(rain_interval_start(row.valid_time)),
                "end": _utc_iso(row.valid_time),
                "precipitation_probability": row.precipitation_probability,
                "precipitation_mm": row.precipitation,
            }
            for row in hours
        ],
        "daily_aggregate": None if day is None else {
            "forecast_date": day.forecast_date.isoformat(),
            "precipitation_probability_max": day.precipitation_probability_max,
            "precipitation_sum_mm": day.precipitation_sum,
        },
        "message_text": message,
    }


async def refresh_and_send_rain_alerts(db: AsyncSession, client: LineClient) -> dict[str, int]:
    """Refresh each user location once, then send daily rain summaries."""
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
            await db.execute(
                select(User.external_id, User.current_location_id).where(
                    User.current_location_id.is_not(None)
                )
            )
        ).all()
    )
    sent = 0
    skipped = 0
    failed = 0
    for external_id, current_location_id in users:
        # Browser fallback identities are valid application users, but they are
        # not LINE Messaging API recipient IDs. LINE user IDs start with "U".
        if not external_id.startswith("U"):
            skipped += 1
            continue

        run = await db.scalar(
            select(ForecastRun)
            .where(ForecastRun.location_id == current_location_id)
            .order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc())
            .limit(1)
        )
        if run is None:
            skipped += 1
            continue
        try:
            if await send_rain_alert(db, run, external_id, client):
                sent += 1
            else:
                skipped += 1
        except LineApiError:
            # A bad/expired recipient must not abort alerts for every user.
            failed += 1
    return {"sent": sent, "skipped": skipped, "failed": failed}


def _location_display_name(location: Location) -> str:
    parts = []
    if location.subdistrict:
        parts.append(f"ต.{location.subdistrict}")
    if location.district:
        parts.append(f"อ.{location.district}")
    if location.province:
        parts.append(f"จ.{location.province}")
    return " ".join(parts) if parts else location.name
