"""P1 transaction-scoped rain serialization. No provider or sender."""
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.models.user import User
from app.notifications.intraday_baseline import read_latest_rain_baseline
from app.notifications.intraday_comparison import (
    Decision, Evidence, POLICY_VERSION, canonical_fingerprint, compare_intraday,
)

from app.notifications.intraday_policy import comparator_for, delivery_prefix


def rain_scope_lock_key(recipient_id: str, location_id: int) -> int:
    """Stable signed bigint; independent of day, run, event and Python hash seed."""
    if not isinstance(recipient_id, str) or not recipient_id.strip():
        raise ValueError("invalid recipient")
    if type(location_id) is not int or location_id <= 0:
        raise ValueError("invalid location")
    encoded = json.dumps(["rain-scope-v1", "line", recipient_id, location_id],
                         separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return int.from_bytes(sha256(encoded).digest()[:8], "big", signed=True)


async def lock_rain_scope(db: AsyncSession, recipient_id: str, location_id: int) -> None:
    """Shared daily/intraday lock, held until caller commits/rolls back.

    SQLite keeps existing daily test behavior; it provides no equivalent lock.
    The locked intraday evaluator below rejects non-PostgreSQL engines.
    """
    key = rain_scope_lock_key(recipient_id, location_id)
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(key)))


@dataclass(frozen=True)
class LockedEvaluation:
    """Decision and owned transaction; valid only inside the context."""
    decision: Decision
    session: AsyncSession


@asynccontextmanager
async def locked_intraday_evaluation(
    sessions: async_sessionmaker[AsyncSession],
    candidate: Evidence,
    *,
    clock: Callable[[], datetime],
    known_location_reassigned: bool = False,
    lock_timeout_ms: int = 3000,
    policy_version: str = POLICY_VERSION,
) -> AsyncIterator[LockedEvaluation]:
    """Recheck under a shared lock; no LINE, ingestion or automatic ledger write.

    Engine-bound READ COMMITTED PostgreSQL is required. The context owns a clean
    transaction, locks current user/location rows, then reads the committed newest
    baseline and event identity. The clock is sampled AFTER acquiring locks.
    A future sender must operate AND persist accepted evidence inside this context.
    Normal exit commits; any exception rolls back and releases locks.
    Without a persisted accepted delivery, subsequent readers may still notify.
    """
    if not isinstance(sessions, async_sessionmaker) or not isinstance(sessions.kw.get("bind"), AsyncEngine):
        raise ValueError("An engine-bound async_sessionmaker is required")
    if sessions.kw["bind"].dialect.name != "postgresql":
        raise ValueError("Locked intraday evaluation requires PostgreSQL")
    if type(lock_timeout_ms) is not int or not 1 <= lock_timeout_ms <= 60000:
        raise ValueError("lock_timeout_ms must be 1..60000")
    if not callable(clock):
        raise ValueError("clock must be callable")
    compare = comparator_for(policy_version)
    async with sessions() as db:
        async with db.begin():
            with db.no_autoflush:
                if not isinstance(candidate, Evidence) or canonical_fingerprint(candidate) is None:
                    yield LockedEvaluation(Decision("skip", ("malformed_input",)), db)
                    return
                scope = candidate.scope
                if not scope.recipient_id.startswith("U"):
                    yield LockedEvaluation(Decision("skip", ("invalid_recipient",)), db)
                    return
                if known_location_reassigned:
                    yield LockedEvaluation(Decision("skip", ("location_reassigned",)), db)
                    return
                isolation = await db.scalar(select(func.current_setting("transaction_isolation")))
                if isolation != "read committed":
                    raise ValueError("READ COMMITTED is required for post-lock rechecks")
                await db.execute(select(func.set_config("lock_timeout", f"{lock_timeout_ms}ms", True)))
                await lock_rain_scope(db, scope.recipient_id, scope.location_id)
                current_location = (await db.execute(
                    select(User.current_location_id)
                    .where(User.external_id == scope.recipient_id).with_for_update()
                )).first()
                reason = None
                if current_location is None or current_location.current_location_id is None:
                    reason = "no_current_location"
                elif current_location.current_location_id != scope.location_id:
                    reason = "location_changed"
                else:
                    location = (await db.execute(
                        select(Location.timezone, Location.is_active)
                        .where(Location.id == scope.location_id).with_for_update(read=True)
                    )).first()
                    if location is None:
                        reason = "no_current_location"
                    elif not location.is_active:
                        reason = "inactive_location"
                    elif location.timezone is None or location.timezone.strip() != scope.timezone.strip():
                        reason = "scope_mismatch"
                if reason:
                    yield LockedEvaluation(Decision("skip", (reason,)), db)
                    return
                baseline = await read_latest_rain_baseline(db, scope)
                decision = (baseline if isinstance(baseline, Decision)
                            else compare(baseline, candidate, now=clock()))
                if decision.outcome == "notify":
                    key = delivery_prefix(policy_version, scope.location_id) + decision.event_id
                    existing = await db.scalar(
                        select(NotificationDelivery.id).where(
                            NotificationDelivery.channel == scope.channel,
                            NotificationDelivery.recipient_id == scope.recipient_id,
                            NotificationDelivery.location_id == scope.location_id,
                            NotificationDelivery.dedupe_key == key,
                        ).limit(1)
                    )
                    if existing is not None:
                        decision = Decision("suppress", ("event_already_delivered",),
                                            decision.window, decision.triggers,
                                            decision.candidate_fingerprint)
                yield LockedEvaluation(decision, db)


async def evaluate_intraday_locked(
    sessions: async_sessionmaker[AsyncSession], candidate: Evidence, *,
    clock: Callable[[], datetime], known_location_reassigned: bool = False,
    lock_timeout_ms: int = 3000,
) -> Decision:
    """Dry-run convenience; returned decision must never authorize a later send."""
    async with locked_intraday_evaluation(
        sessions, candidate, clock=clock,
        known_location_reassigned=known_location_reassigned,
        lock_timeout_ms=lock_timeout_ms,
    ) as evaluation:
        return evaluation.decision
