"""Committed snapshot input and preview-only entrypoint; no provider or LINE client."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import ForecastRun, HourlyForecast, Location, User
from app.notifications.intraday_comparison import Decision, Evidence, Hour, Scope, canonical_fingerprint
from app.notifications.intraday_delivery import IntradayDeliveryResult, deliver_intraday_update
from app.notifications.intraday_formatter import utc


def _engine(sessions):
    if not isinstance(sessions, async_sessionmaker):
        raise ValueError("An engine-bound PostgreSQL session factory is required")
    engine = sessions.kw.get("bind")
    if not isinstance(engine, AsyncEngine) or engine.dialect.name != "postgresql":
        raise ValueError("An engine-bound PostgreSQL session factory is required")
    return engine


async def read_committed_candidate(
    sessions: async_sessionmaker[AsyncSession], recipient_id: str, *, now: datetime,
) -> Evidence | Decision:
    """Read one consistent committed view, newest run first; never fall back.

    A private repeatable-read, read-only transaction prevents mixed versions
    across assignment/run/hour queries. This transaction ends before the
    delivery module obtains its READ COMMITTED scope locks and verifies again.
    No provider refresh is performed. Hour.valid_time denotes interval end.
    """
    _engine(sessions)
    if not isinstance(recipient_id, str) or not recipient_id.startswith("U"):
        return Decision("skip", ("invalid_recipient",))
    now = utc(now)
    async with sessions(autoflush=False) as db:
        async with db.begin():
            await db.execute(text(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            ))
            await db.execute(text("SELECT set_config('statement_timeout', '3000', true)"))
            assignment = (await db.execute(
                select(User.current_location_id, Location.timezone, Location.is_active)
                .outerjoin(Location, Location.id == User.current_location_id)
                .where(User.external_id == recipient_id)
            )).first()
            if assignment is None or assignment.current_location_id is None:
                return Decision("skip", ("no_current_location",))
            if not assignment.is_active:
                return Decision("skip", ("inactive_location",))
            try:
                zone_name = assignment.timezone.strip()
                zone = ZoneInfo(zone_name)
            except (AttributeError, ValueError, ZoneInfoNotFoundError):
                return Decision("skip", ("invalid_timezone",))
            run = (await db.execute(
                select(ForecastRun.id, ForecastRun.provider, ForecastRun.retrieved_at,
                       ForecastRun.model_run_time)
                .where(ForecastRun.location_id == assignment.current_location_id)
                .order_by(ForecastRun.retrieved_at.desc(), ForecastRun.id.desc())
                .limit(1)
            )).first()
            if run is None:
                return Decision("skip", ("no_committed_snapshot",))
            rows = (await db.execute(
                select(HourlyForecast.valid_time, HourlyForecast.precipitation_probability,
                       HourlyForecast.precipitation)
                .where(HourlyForecast.forecast_run_id == run.id)
                .order_by(HourlyForecast.valid_time, HourlyForecast.id)
            )).all()
            day = now.astimezone(zone).date()
            hours = tuple(
                Hour(utc(row.valid_time) - timedelta(hours=1), utc(row.valid_time),
                     row.precipitation_probability, row.precipitation)
                for row in rows
                if (utc(row.valid_time) - timedelta(hours=1)).astimezone(zone).date() == day
            )
            if not hours:
                return Decision("skip", ("no_snapshot_hours_for_local_day",))
            candidate = Evidence(
                Scope(recipient_id, assignment.current_location_id, run.provider, zone_name),
                run.id, utc(run.retrieved_at), hours,
                None if run.model_run_time is None else utc(run.model_run_time),
            )
            if canonical_fingerprint(candidate) is None:
                return Decision("skip", ("malformed_committed_snapshot",))
            return candidate


@dataclass(frozen=True)
class PreviewResult:
    recipient_id: str
    source_id: int | None
    result: IntradayDeliveryResult


async def preview_committed_snapshots(
    sessions: async_sessionmaker[AsyncSession], recipient_ids: Iterable[str], *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[PreviewResult, ...]:
    """Evaluate explicit recipients in stable order, once each, with fresh clocks.

    There is deliberately no client or live-send option. DB failures are
    reported as errors, never as missing evidence or retryable send permission.
    Exception text/credentials are not exposed. Cancellation propagates.
    """
    _engine(sessions)
    supplied = tuple(recipient_ids)
    if any(not isinstance(item, str) for item in supplied):
        raise ValueError("Recipients must be strings")
    recipients = tuple(sorted(set(supplied)))
    results = []
    for recipient in recipients:
        source_id = None
        try:
            candidate = await read_committed_candidate(sessions, recipient, now=clock())
            if isinstance(candidate, Decision):
                result = IntradayDeliveryResult(candidate.outcome, candidate)
            else:
                source_id = candidate.source_id
                result = await deliver_intraday_update(
                    sessions, candidate, clock=clock, client=None, dry_run=True,
                    policy_version=settings.INTRADAY_POLICY_VERSION,
                )
        except SQLAlchemyError:
            result = IntradayDeliveryResult("error", Decision("skip", ("database_error",)))
        results.append(PreviewResult(recipient, source_id, result))
    return tuple(results)
