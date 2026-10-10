"""Explicitly enabled, allowlisted live adapter over the existing locked sender."""
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.notifications.intraday_comparison import Decision
from app.notifications.intraday_delivery import (
    AcceptedDeliveryNotCommitted, IntradayDeliveryResult, SendOutcomeUnknown, deliver_intraday_update,
)
from app.notifications.intraday_preview import PreviewResult, _engine, read_committed_candidate
from app.notifications.line_client import LineApiError, LineClient


async def send_committed_snapshots(sessions, recipient_ids, *,
                                   clock=lambda: datetime.now(timezone.utc)):
    _engine(sessions)
    if not settings.INTRADAY_SEND_ENABLED:
        return ()
    allowed = {x.strip() for x in settings.INTRADAY_SEND_RECIPIENT_IDS.split(",") if x.strip()}
    if not settings.LINE_CHANNEL_ACCESS_TOKEN or not allowed or any(not x.startswith("U") for x in allowed):
        raise ValueError("Live intraday token and explicit LINE allowlist required")
    client = LineClient(settings.LINE_CHANNEL_ACCESS_TOKEN, settings.LINE_API_BASE_URL)
    results = []
    for recipient in sorted(set(recipient_ids)):
        source_id = None
        if recipient not in allowed:
            result = IntradayDeliveryResult("skip", Decision("skip", ("recipient_not_authorized",)))
        else:
            try:
                candidate = await read_committed_candidate(sessions, recipient, now=clock())
                if isinstance(candidate, Decision):
                    result = IntradayDeliveryResult(candidate.outcome, candidate)
                else:
                    source_id = candidate.source_id
                    result = await deliver_intraday_update(
                        sessions, candidate, clock=clock, client=client,
                        dry_run=False, durable_attempts=True,
                        policy_version=settings.INTRADAY_POLICY_VERSION,
                    )
            except (SendOutcomeUnknown, AcceptedDeliveryNotCommitted):
                result = IntradayDeliveryResult("error", Decision("skip", ("send_requires_reconciliation",)))
            except LineApiError:
                # No automatic rejection retry. Pending intent remains blocked.
                result = IntradayDeliveryResult("error", Decision("skip", ("line_rejected_reconciliation_required",)))
            except SQLAlchemyError:
                result = IntradayDeliveryResult("error", Decision("skip", ("database_error",)))
        results.append(PreviewResult(recipient, source_id, result))
    return tuple(results)
