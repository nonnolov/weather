"""Intraday delivery integration. Default is preview; no CLI/scheduler hook."""
import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Protocol, Literal
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.forecast import ForecastRun, HourlyForecast
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.notifications.intraday_baseline import _adapt, read_latest_rain_baseline
from app.notifications.intraday_comparison import (
    Baseline, Decision, Evidence, Hour, POLICY_VERSION, canonical_fingerprint, compare_intraday,
)
from app.notifications.intraday_formatter import format_intraday_alert, freeze_intraday_evidence, utc
from app.notifications.rain_locking import locked_intraday_evaluation


class TextSender(Protocol):
    async def push_text(self, recipient_id: str, text: str) -> None: ...


class AcceptedDeliveryNotCommitted(RuntimeError):
    """Push returned normally, but evidence could not be committed. Never auto-retry."""
    def __init__(self, event_id: str):
        self.event_id = event_id
        super().__init__("LINE accepted the update but durable evidence was not confirmed")


class SendOutcomeUnknown(RuntimeError):
    """Timeout can hide acceptance. No automatic retry or baseline advancement."""
    def __init__(self, event_id: str):
        self.event_id = event_id
        super().__init__("LINE acceptance is unknown after a transport error; do not auto-retry")


@dataclass(frozen=True)
class IntradayDeliveryResult:
    status: Literal["preview", "sent", "skip", "suppress"]
    decision: Decision
    message: str | None = None
    delivery_id: int | None = None


async def _verify_candidate(db: AsyncSession, candidate: Evidence, *, now: datetime) -> bool:
    """Only committed same-location source rows may back a new delivery.

    Candidate input must contain all supplied rows for the current local-start day.
    Share locks protect the run and existing hourly rows until commit.
    """
    if type(candidate.source_id) is not int:
        return False
    run = (await db.execute(
        select(ForecastRun.location_id, ForecastRun.provider, ForecastRun.retrieved_at,
               ForecastRun.model_run_time).where(ForecastRun.id == candidate.source_id)
        .with_for_update(read=True)
    )).first()
    if run is None or run.location_id != candidate.scope.location_id:
        return False
    if utc(run.retrieved_at) != utc(candidate.retrieved_at):
        return False
    if (None if run.model_run_time is None else utc(run.model_run_time)) != (
            None if candidate.model_time is None else utc(candidate.model_time)):
        return False
    zone = ZoneInfo(candidate.scope.timezone.strip())
    day = utc(now).astimezone(zone).date()
    rows = (await db.execute(
        select(HourlyForecast.valid_time, HourlyForecast.precipitation_probability,
               HourlyForecast.precipitation)
        .where(HourlyForecast.forecast_run_id == candidate.source_id)
        .order_by(HourlyForecast.valid_time).with_for_update(read=True)
    )).all()
    hours = tuple(Hour(utc(row.valid_time) - timedelta(hours=1), utc(row.valid_time),
                       row.precipitation_probability, row.precipitation)
                  for row in rows if (utc(row.valid_time) - timedelta(hours=1)).astimezone(zone).date() == day)
    scope = candidate.scope
    persisted = Evidence(replace(scope, provider=run.provider), candidate.source_id,
                         run.retrieved_at, hours, run.model_run_time)
    return canonical_fingerprint(persisted) == canonical_fingerprint(candidate)


async def _historical_replay(db: AsyncSession, candidate: Evidence,
                             baseline_id: int, now: datetime) -> Decision | None:
    """Verify committed v1 intraday history without mutating or inventing a ledger."""
    scope = candidate.scope
    prefix = f"rain-intraday:v1:{scope.location_id}:"
    rows = (await db.execute(
        select(NotificationDelivery.id, NotificationDelivery.created_at,
               NotificationDelivery.forecast_run_id, NotificationDelivery.rain_evidence,
               NotificationDelivery.dedupe_key)
        .where(NotificationDelivery.channel == scope.channel,
               NotificationDelivery.recipient_id == scope.recipient_id,
               NotificationDelivery.location_id == scope.location_id,
               NotificationDelivery.dedupe_key.startswith(prefix))
    )).all()
    fingerprint = canonical_fingerprint(candidate)
    day = utc(now).astimezone(ZoneInfo(scope.timezone.strip())).date().isoformat()
    for row in rows:
        adapted = _adapt(row, scope)
        if not isinstance(adapted, Baseline) or adapted.evidence is None:
            return Decision("skip", ("unknown_replay_history",))
        data = row.rain_evidence
        comparison = data.get("comparison")
        old_hash = canonical_fingerprint(adapted.evidence)
        if (not isinstance(comparison, dict)
                or comparison.get("policy_version") != POLICY_VERSION
                or type(comparison.get("baseline_delivery_id")) is not int
                or comparison["baseline_delivery_id"] <= 0
                or comparison.get("candidate_fingerprint") != old_hash
                or not isinstance(comparison.get("event_id"), str)
                or len(comparison["event_id"]) != 64
                or any(char not in "0123456789abcdef" for char in comparison["event_id"])
                or row.dedupe_key != prefix + comparison["event_id"]):
            return Decision("skip", ("unknown_replay_history",))
        same_day_scope = (data["alert_local_date"] == day
                          and adapted.evidence.scope.timezone.strip() == scope.timezone.strip())
        if same_day_scope and adapted.evidence.source_id == candidate.source_id and old_hash != fingerprint:
            return Decision("skip", ("inconsistent_historical_replay",))
        if (comparison["baseline_delivery_id"] == baseline_id and same_day_scope
                and old_hash == fingerprint):
            return Decision("suppress", ("historical_identical_content",))
    return None


async def deliver_intraday_update(
    sessions: async_sessionmaker[AsyncSession], candidate: Evidence, *,
    clock: Callable[[], datetime], client: TextSender | None = None,
    dry_run: bool = True, known_location_reassigned: bool = False,
    lock_timeout_ms: int = 3000,
) -> IntradayDeliveryResult:
    """Render/verify under lock, optionally push and persist; return after commit.

    This step is only exercised with mocks. No runtime entrypoint calls it.
    Default preview neither pushes nor inserts a delivery. A send requires an
    explicitly supplied client and dry_run=False; there is no internal retry.
    Timeout is ambiguous; post-acceptance persistence failure is explicitly raised.
    """
    if not callable(clock):
        raise ValueError("clock must be callable")
    if type(dry_run) is not bool:
        raise ValueError("dry_run must be boolean")
    if not dry_run and client is None:
        raise ValueError("Explicit client is required for sending")
    accepted = False
    event_id = None
    sampled = []
    def decision_clock():
        value = clock()
        sampled.append(value)
        return value
    try:
        async with locked_intraday_evaluation(
            sessions, candidate, clock=decision_clock,
            known_location_reassigned=known_location_reassigned,
            lock_timeout_ms=lock_timeout_ms,
        ) as evaluation:
            db, decision = evaluation.session, evaluation.decision
            if decision.outcome != "notify":
                return IntradayDeliveryResult(decision.outcome, decision)
            now = sampled[0]
            if not await _verify_candidate(db, candidate, now=now):
                return IntradayDeliveryResult("skip", Decision("skip", ("candidate_source_mismatch",)))
            baseline = await read_latest_rain_baseline(db, candidate.scope)
            if not isinstance(baseline, Baseline) or baseline.evidence is None:
                return IntradayDeliveryResult("skip", Decision("skip", ("baseline_changed",)))
            # Candidate/source reads may themselves wait. Freeze the final decision
            # clock after those locks, then recheck identity before any network await.
            now = clock()
            decision = compare_intraday(baseline, candidate, now=now)
            if decision.outcome != "notify":
                return IntradayDeliveryResult(decision.outcome, decision)
            key = f"rain-intraday:v1:{candidate.scope.location_id}:{decision.event_id}"
            existing = await db.scalar(select(NotificationDelivery.id).where(
                NotificationDelivery.channel == candidate.scope.channel,
                NotificationDelivery.recipient_id == candidate.scope.recipient_id,
                NotificationDelivery.location_id == candidate.scope.location_id,
                NotificationDelivery.dedupe_key == key,
            ).limit(1))
            if existing is not None:
                return IntradayDeliveryResult("suppress", Decision(
                    "suppress", ("event_already_delivered",), decision.window,
                    decision.triggers, decision.candidate_fingerprint))
            replay = await _historical_replay(db, candidate, baseline.delivery_id, now)
            if replay is not None:
                return IntradayDeliveryResult(replay.outcome, replay)
            location_name = await db.scalar(select(Location.name).where(Location.id == candidate.scope.location_id))
            rendered = format_intraday_alert(candidate, decision, now=now, location_name=location_name)
            frozen = freeze_intraday_evidence(candidate, decision, rendered, now=now,
                                               baseline_delivery_id=baseline.delivery_id)
            if dry_run:
                return IntradayDeliveryResult("preview", decision, rendered.message)
            event_id = decision.event_id
            try:
                await client.push_text(candidate.scope.recipient_id, rendered.message)
            except (TimeoutError, httpx.TransportError) as error:
                raise SendOutcomeUnknown(event_id) from error
            except asyncio.CancelledError as error:
                error.add_note("LINE acceptance may be unknown after cancellation; do not auto-retry")
                raise
            accepted = True
            accepted_at = utc(clock())
            if accepted_at < utc(now):
                raise ValueError("Acceptance clock precedes evaluation")
            delivery = NotificationDelivery(
                location_id=candidate.scope.location_id, channel=candidate.scope.channel,
                recipient_id=candidate.scope.recipient_id,
                dedupe_key=f"rain-intraday:v1:{candidate.scope.location_id}:{event_id}",
                forecast_run_id=candidate.source_id, rain_evidence=frozen, created_at=accepted_at,
            )
            db.add(delivery)
            await db.flush()
            result = IntradayDeliveryResult("sent", decision, rendered.message, delivery.id)
        # The context's commit has completed. A flush alone never reports success.
        return result
    except Exception as error:
        if accepted:
            raise AcceptedDeliveryNotCommitted(event_id) from error
        raise
