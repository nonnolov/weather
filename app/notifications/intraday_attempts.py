"""Commit send intent before network I/O; pending intents require reconciliation."""
from sqlalchemy import or_, select, text
from app.models.intraday_attempt import IntradaySendAttempt


async def reserve_attempt(sessions, candidate, decision, frozen, now):
    # Caller owns the existing recipient/location rain-scope lock. This separate
    # transaction deliberately survives rollback/crash of the sender transaction.
    async with sessions() as db:
        await db.execute(text("SELECT set_config('lock_timeout', '3000ms', true)"))
        await db.execute(text("SELECT set_config('statement_timeout', '5000ms', true)"))
        blocked = await db.scalar(select(IntradaySendAttempt.id).where(
            IntradaySendAttempt.recipient_id == candidate.scope.recipient_id,
            IntradaySendAttempt.location_id == candidate.scope.location_id,
            or_(IntradaySendAttempt.status == "pending",
                IntradaySendAttempt.event_id == decision.event_id),
        ).limit(1))
        if blocked is not None:
            return None
        attempt = IntradaySendAttempt(
            recipient_id=candidate.scope.recipient_id,
            location_id=candidate.scope.location_id, event_id=decision.event_id,
            status="pending", evidence=frozen, created_at=now,
        )
        db.add(attempt)
        await db.flush()
        attempt_id = attempt.id
        await db.commit()
        return attempt_id
