"""Bounded, default-off previews after explicit forecast refresh commits."""
import asyncio
import logging
from collections import Counter

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.notifications.subscriptions import recipient_condition

logger = logging.getLogger(__name__)
_QUEUE = "intraday_preview_committed_runs"
MAX_RECIPIENTS = 100
PREVIEW_TIMEOUT_SECONDS = 15


def queue_forecast_preview(db: AsyncSession, location_id: int, run_id: int) -> None:
    """Queue identity only. Never evaluate uncommitted ORM state or send."""
    if not settings.INTRADAY_PREVIEW_AFTER_REFRESH:
        return
    if any(type(value) is not int or value <= 0 for value in (location_id, run_id)):
        raise ValueError("Positive database identities are required")
    db.info.setdefault(_QUEUE, {})[location_id] = run_id


def discard_forecast_previews(db: AsyncSession) -> None:
    db.info.pop(_QUEUE, None)


async def _evaluate(sessions, queued):
    from app.models import ForecastRun, Location, User
    from app.notifications.intraday_preview import preview_committed_snapshots
    async with sessions(autoflush=False) as reader:
        committed = set((await reader.scalars(
            select(ForecastRun.id).where(
                tuple_(ForecastRun.location_id, ForecastRun.id).in_(list(queued.items())))
        )).all())
        locations = [location for location, run in queued.items() if run in committed]
        if not locations:
            return (), False
        recipients = list((await reader.scalars(
            select(User.external_id).join(Location, Location.id == User.current_location_id)
            .where(User.current_location_id.in_(locations), Location.is_active.is_(True),
                   recipient_condition())
            .order_by(User.external_id).limit(MAX_RECIPIENTS + 1)
        )).all())
    # Release the discovery transaction before owned candidate/locking sessions.
    return await preview_committed_snapshots(sessions, recipients[:MAX_RECIPIENTS]), len(recipients) > MAX_RECIPIENTS


async def run_forecast_previews(db: AsyncSession, sessions):
    """Consume once AFTER successful commit; failures cannot roll back source.

    In-memory best effort, not a durable queue. No retries, client, ingestion,
    provider call or accepted-delivery write. A lost preview is safe to lose.
    """
    if db.in_transaction():
        raise ValueError("Preview requires the source transaction to have ended")
    queued = db.info.pop(_QUEUE, {})
    if not settings.INTRADAY_PREVIEW_AFTER_REFRESH or not queued:
        return ()
    try:
        async with asyncio.timeout(PREVIEW_TIMEOUT_SECONDS):
            results, truncated = await _evaluate(sessions, queued)
        statuses = Counter(item.result.status for item in results)
        reasons = Counter(reason for item in results for reason in item.result.decision.reasons)
        logger.info("Intraday preview: processed=%s statuses=%s reasons=%s truncated=%s",
                    len(results), dict(statuses), dict(reasons), truncated)
        return results
    except Exception:
        # Intentionally omit traceback, exception strings and all identifiers.
        # asyncio.CancelledError remains cancellation and propagates.
        logger.warning("Intraday preview failed after source commit; no retry")
        return ()
