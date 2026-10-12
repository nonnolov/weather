"""Forecast-only periodic previews or explicitly enabled intraday delivery."""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import settings
from app.notifications.subscriptions import recipient_condition
from app.models import ForecastRun, Location, User
from app.notifications.intraday_formatter import utc

logger = logging.getLogger(__name__)
POLL_SECONDS = 15 * 60
STARTUP_DELAY_SECONDS = 60
REFRESH_AGE = timedelta(hours=1)
CYCLE_TIMEOUT_SECONDS = 120
PREVIEW_TIMEOUT_SECONDS = 15
MAX_LOCATIONS = 10
MAX_RECIPIENTS = 100
# Dedicated namespace, distinct from recipient rain-scope/daily dedupe locks.
CYCLE_LOCK_KEY = 57869370623934001


@dataclass
class CycleReport:
    status: str = "complete"
    locations: int = 0
    refreshed: int = 0
    fresh: int = 0
    refresh_failed: int = 0
    processed: int = 0
    statuses: dict = field(default_factory=dict)
    reasons: dict = field(default_factory=dict)
    truncated: bool = False


def _validate_factory(sessions):
    if not isinstance(sessions, async_sessionmaker):
        raise ValueError("An engine-bound PostgreSQL session factory is required")
    engine = sessions.kw.get("bind")
    if not isinstance(engine, AsyncEngine) or engine.dialect.name != "postgresql":
        raise ValueError("An engine-bound PostgreSQL session factory is required")


async def _refresh_if_due(sessions, location_id, clock):
    from app.ingestion.service import ingest_forecast_for_location
    async with sessions() as db:
        await db.execute(text("SELECT set_config('lock_timeout', '3000ms', true)"))
        await db.execute(text("SELECT set_config('statement_timeout', '5000ms', true)"))
        location = await db.scalar(
            select(Location).where(Location.id == location_id).with_for_update()
        )
        assigned = await db.scalar(select(User.external_id).where(
            User.current_location_id == location_id, recipient_condition()
        ).limit(1))
        if location is None or not location.is_active or assigned is None:
            return "out_of_scope"
        latest = await db.scalar(select(ForecastRun.retrieved_at)
            .where(ForecastRun.location_id == location_id)
            .order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc()).limit(1))
        if latest is not None and utc(clock()) - utc(latest) < REFRESH_AGE:
            return "fresh"
        await ingest_forecast_for_location(db, location, forecast_days=7)
        await db.commit()
        return "refreshed"


async def _cycle(sessions, clock, report):
    from collections import Counter
    from app.notifications.intraday_preview import preview_committed_snapshots
    # One coordinator transaction holds a PostgreSQL try-lock for the complete
    # cycle. Different replicas/processes skip immediately instead of waiting.
    async with sessions() as coordinator:
        async with coordinator.begin():
            await coordinator.execute(text("SELECT set_config('statement_timeout', '5000ms', true)"))
            acquired = await coordinator.scalar(select(func.pg_try_advisory_xact_lock(CYCLE_LOCK_KEY)))
            if not acquired:
                report.status = "busy"
                return
            # Oldest source first avoids starvation when the bounded batch fills.
            ids = list((await coordinator.scalars(
                select(Location.id).join(User, User.current_location_id == Location.id)
                .outerjoin(ForecastRun, ForecastRun.location_id == Location.id)
                .where(Location.is_active.is_(True), recipient_condition())
                .group_by(Location.id)
                .order_by(func.max(ForecastRun.retrieved_at).asc().nullsfirst(), Location.id)
                .limit(MAX_LOCATIONS + 1)
            )).all())
            report.truncated = len(ids) > MAX_LOCATIONS
            report.locations = min(len(ids), MAX_LOCATIONS)
            eligible = []
            for location_id in ids[:MAX_LOCATIONS]:
                try:
                    result = await _refresh_if_due(sessions, location_id, clock)
                except Exception:
                    # No exception text, identifiers, provider URLs or retries.
                    report.refresh_failed += 1
                    continue
                if result == "out_of_scope":
                    continue
                setattr(report, result, getattr(report, result) + 1)
                eligible.append(location_id)
            if not eligible:
                return
            async with sessions() as reader:
                recipients = list((await reader.scalars(
                    select(User.external_id).join(Location, Location.id == User.current_location_id)
                    .where(User.current_location_id.in_(eligible), Location.is_active.is_(True),
                           recipient_condition())
                    .order_by(User.external_id).limit(MAX_RECIPIENTS + 1)
                )).all())
            report.truncated |= len(recipients) > MAX_RECIPIENTS
            if settings.INTRADAY_SEND_ENABLED:
                from app.notifications.intraday_live import send_committed_snapshots
                async with asyncio.timeout(90):
                    results = await send_committed_snapshots(sessions, recipients[:MAX_RECIPIENTS], clock=clock)
            else:
                async with asyncio.timeout(PREVIEW_TIMEOUT_SECONDS):
                    results = await preview_committed_snapshots(sessions, recipients[:MAX_RECIPIENTS], clock=clock)
            report.processed = len(results)
            report.statuses = dict(Counter(p.result.status for p in results))
            report.reasons = dict(Counter(r for p in results for r in p.result.decision.reasons))


async def run_scheduled_preview_cycle(sessions, *, clock=lambda: datetime.now(timezone.utc)):
    """Commit due forecasts, then preview or explicitly enabled live intraday.

    The daily CLI/observations are never invoked. Preview is the default.

    Future scheduled ticks may attempt a failed forecast again. No immediate
    retries of LINE sends. Preview never writes accepted deliveries. Cancellation
    propagates; already
    committed snapshots survive any later failure.
    """
    if not settings.INTRADAY_PREVIEW_SCHEDULER_ENABLED:
        return CycleReport(status="disabled")
    _validate_factory(sessions)
    report = CycleReport()
    try:
        async with asyncio.timeout(CYCLE_TIMEOUT_SECONDS):
            await _cycle(sessions, clock, report)
    except TimeoutError:
        report.status = "timeout"
    except Exception:
        report.status = "error"
    label = "live" if settings.INTRADAY_SEND_ENABLED else "preview"
    logger.info("Scheduled intraday %s: status=%s locations=%s refreshed=%s fresh=%s "
                "refresh_failed=%s processed=%s statuses=%s reasons=%s truncated=%s",
                label, report.status, report.locations, report.refreshed, report.fresh,
                report.refresh_failed, report.processed, report.statuses,
                report.reasons, report.truncated)
    return report


async def _serve(sessions):
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        await run_scheduled_preview_cycle(sessions)
        # Delay from completion: no overlapping ticks or catch-up storm.
        await asyncio.sleep(POLL_SECONDS)


@asynccontextmanager
async def scheduled_preview_lifespan(app):
    """No task/DB/provider work when disabled; API startup stays non-blocking."""
    if not settings.INTRADAY_PREVIEW_SCHEDULER_ENABLED:
        yield
        return
    from app.core.database import AsyncSessionLocal
    _validate_factory(AsyncSessionLocal)
    task = asyncio.create_task(_serve(AsyncSessionLocal), name="intraday-preview-scheduler")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
