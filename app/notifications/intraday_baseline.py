"""Read-only P1 baseline integration; deliberately has no sender or CLI hook.

The factory must be engine-bound (not bound to a caller's uncommitted connection).
An owned session reads committed history, without autoflush or identity-map reuse.
A notify decision is eligibility only, never authorization to send.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.models.user import User
from app.notifications.intraday_policy import SUPPORTED_POLICIES, delivery_prefix
from app.notifications.intraday_comparison import (
    Baseline, Decision, Evidence, Hour, Scope, canonical_fingerprint, compare_intraday,
)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    return datetime.fromisoformat(value)


def _adapt(row, scope: Scope) -> Baseline | Decision:
    """Use frozen JSON only; a missing source FK does not erase provenance."""
    payload = row.rain_evidence
    if payload is None:
        return Baseline(row.id, row.created_at, None)
    if not isinstance(payload, dict):
        return Decision("skip", ("malformed_baseline_evidence",))
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        return Decision("skip", ("unsupported_baseline",))
    try:
        source = payload["source"]
        if not isinstance(source, dict):
            raise ValueError("invalid source")
        rows = payload["hourly_intervals"]
        if not isinstance(rows, list):
            raise ValueError("invalid hourly rows")
        frozen_scope = Scope(scope.recipient_id, scope.location_id,
                             source["provider"], payload["timezone"], scope.channel)
        hours = []
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError("invalid hour")
            # Missing metrics remain unknown, never default to zero.
            hours.append(Hour(_timestamp(item["start"]), _timestamp(item["end"]),
                              item.get("precipitation_probability"),
                              item.get("precipitation_mm")))
        model = source.get("model_run_time")
        evidence = Evidence(frozen_scope, source["forecast_run_id"],
                            _timestamp(source["retrieved_at"]), tuple(hours),
                            None if model is None else _timestamp(model))
        if canonical_fingerprint(evidence) is None:
            raise ValueError("invalid frozen evidence")
        if row.forecast_run_id is not None and row.forecast_run_id != evidence.source_id:
            raise ValueError("conflicting source identity")
        # Frozen day metadata cannot silently disagree with supplied intervals.
        day = date.fromisoformat(payload["alert_local_date"])
        zone = ZoneInfo(frozen_scope.timezone.strip())
        if any((hour.start.replace(tzinfo=timezone.utc) if hour.start.tzinfo is None
                else hour.start).astimezone(zone).date() != day for hour in hours):
            raise ValueError("conflicting local day")
        return Baseline(row.id, row.created_at, evidence)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError):
        return Decision("skip", ("malformed_baseline_evidence",))


async def read_latest_rain_baseline(db: AsyncSession, scope: Scope) -> Baseline | Decision | None:
    """Select newest daily/supported intraday delivery, without evidence filtering.

    The caller must supply a clean, committed-history session. Do not use this
    helper alone as a pre-send check. Unknown newest evidence never falls back.
    created_at is the stored acceptance proxy, not handset receipt time.
    """
    daily = f"rain:{scope.location_id}:"
    intraday = [delivery_prefix(policy, scope.location_id) for policy in SUPPORTED_POLICIES]
    with db.no_autoflush:
        row = (await db.execute(
            select(NotificationDelivery.id, NotificationDelivery.created_at,
                   NotificationDelivery.forecast_run_id, NotificationDelivery.rain_evidence)
            .where(NotificationDelivery.channel == scope.channel,
                   NotificationDelivery.recipient_id == scope.recipient_id,
                   NotificationDelivery.location_id == scope.location_id,
                   or_(NotificationDelivery.dedupe_key.startswith(daily),
                       *(NotificationDelivery.dedupe_key.startswith(prefix) for prefix in intraday)))
            .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
            .limit(1)
        )).first()
    return None if row is None else _adapt(row, scope)


async def evaluate_intraday_from_db(
    sessions: async_sessionmaker[AsyncSession],
    candidate: Evidence,
    *,
    now: datetime,
    known_location_reassigned: bool = False,
) -> Decision:
    """Read committed baseline/current assignment and return a dry-run decision.

    No flush/commit, provider call, delivery insertion, lock, or LINE call.
    DB errors propagate; they must not be interpreted as absent history.
    This is a read-time preview, not an atomic pre-send authorization.
    """
    if not isinstance(sessions, async_sessionmaker) or not isinstance(sessions.kw.get("bind"), AsyncEngine):
        raise ValueError("An engine-bound async_sessionmaker is required for committed-history reads")
    if not isinstance(candidate, Evidence) or canonical_fingerprint(candidate) is None:
        return Decision("skip", ("malformed_input",))
    scope = candidate.scope
    if not scope.recipient_id.startswith("U"):
        return Decision("skip", ("invalid_recipient",))
    if known_location_reassigned:
        return Decision("skip", ("location_reassigned",))
    async with sessions() as db:
        with db.no_autoflush:
            assignment = (await db.execute(
                select(User.current_location_id, Location.timezone, Location.is_active)
                .outerjoin(Location, Location.id == User.current_location_id)
                .where(User.external_id == scope.recipient_id)
            )).first()
            if assignment is None or assignment.current_location_id is None:
                return Decision("skip", ("no_current_location",))
            if assignment.current_location_id != scope.location_id:
                return Decision("skip", ("location_changed",))
            if not assignment.is_active:
                return Decision("skip", ("inactive_location",))
            if assignment.timezone is None or assignment.timezone.strip() != scope.timezone.strip():
                return Decision("skip", ("scope_mismatch",))
            baseline = await read_latest_rain_baseline(db, scope)
        if isinstance(baseline, Decision):
            return baseline
        return compare_intraday(baseline, candidate, now=now)
