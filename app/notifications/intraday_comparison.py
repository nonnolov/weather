"""Pure P1 comparison. No lookup, sending, settings, or persistence.

Callers adapt frozen v1 hourly evidence (including unselected hours) to these
immutable records. Supply the newest durable accepted delivery only; never fall
back to an older record. Naive datetimes mean UTC. Intervals use (start, end].
The candidate's absolute hourly phase defines the grid, independent of display
zone. The window fills every grid slot, including missing leading/trailing rows.
Unknown location reassignment and committed replay history remain caller duties.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
from typing import Literal
from zoneinfo import ZoneInfo


POLICY_VERSION = "intraday-v1"
HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class Scope:
    recipient_id: str
    location_id: int
    provider: str
    timezone: str
    channel: str = "line"


@dataclass(frozen=True)
class Hour:
    start: datetime
    end: datetime
    probability: float | int | Decimal | None
    rainfall_mm: float | int | Decimal | None


@dataclass(frozen=True)
class Evidence:
    scope: Scope
    source_id: str | int
    retrieved_at: datetime
    hours: tuple[Hour, ...]
    model_time: datetime | None = None
    schema_version: int = 1


@dataclass(frozen=True)
class Baseline:
    delivery_id: str | int
    accepted_at: datetime
    evidence: Evidence | None


@dataclass(frozen=True)
class Trigger:
    """Aligned immutable values explaining significance, not display ranking."""

    reason: Literal["earlier_onset", "new_rain", "escalation"]
    baseline: Hour
    candidate: Hour


@dataclass(frozen=True)
class Decision:
    outcome: Literal["skip", "suppress", "notify"]
    reasons: tuple[str, ...]
    window: tuple[tuple[datetime, datetime], ...] = ()
    triggers: tuple[Trigger, ...] = ()
    candidate_fingerprint: str | None = None
    event_id: str | None = None


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("invalid timestamp")
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _identifier(value: object) -> bool:
    return (type(value) is int and value > 0) or (type(value) is str and bool(value.strip()))


def _number(value: object, *, probability: bool) -> str | None:
    if value is None:
        return None
    if type(value) not in (int, float, Decimal):
        raise ValueError("invalid metric")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0 or (probability and number > 100):
        raise ValueError("invalid metric")
    # Fixed formatting avoids Decimal context rounding and normalizes 70/70.0.
    result = format(number, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return "0" if number == 0 else result


def _normalize(evidence: Evidence) -> Evidence:
    if not isinstance(evidence, Evidence) or type(evidence.schema_version) is not int or evidence.schema_version != 1:
        raise ValueError("unsupported evidence")
    scope = evidence.scope
    if not isinstance(scope, Scope) or scope.channel != "line":
        raise ValueError("invalid scope")
    if not isinstance(scope.recipient_id, str) or not scope.recipient_id.strip():
        raise ValueError("invalid recipient")
    if type(scope.location_id) is not int or scope.location_id <= 0:
        raise ValueError("invalid location")
    if not isinstance(scope.provider, str) or not scope.provider.strip():
        raise ValueError("invalid provider")
    if not isinstance(scope.timezone, str):
        raise ValueError("invalid timezone")
    zone = ZoneInfo(scope.timezone.strip())
    if not _identifier(evidence.source_id) or type(evidence.hours) is not tuple:
        raise ValueError("invalid evidence")
    hours = []
    keys = set()
    for row in evidence.hours:
        if not isinstance(row, Hour):
            raise ValueError("invalid hour")
        start, end = _utc(row.start), _utc(row.end)
        if end - start != HOUR or (start, end) in keys:
            raise ValueError("invalid or duplicate interval")
        keys.add((start, end))
        probability = _number(row.probability, probability=True)
        rainfall = _number(row.rainfall_mm, probability=False)
        hours.append(Hour(start, end, None if probability is None else Decimal(probability),
                          None if rainfall is None else Decimal(rainfall)))
    return Evidence(
        Scope(scope.recipient_id, scope.location_id, scope.provider.strip().casefold(), zone.key),
        evidence.source_id, _utc(evidence.retrieved_at),
        tuple(sorted(hours, key=lambda row: (row.start, row.end))),
        None if evidence.model_time is None else _utc(evidence.model_time),
    )


def _hour_content(row: Hour) -> list:
    return [row.start.isoformat(), row.end.isoformat(),
            _number(row.probability, probability=True),
            _number(row.rainfall_mm, probability=False)]


def _digest(value: object) -> str:
    return sha256(json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def _fingerprint(evidence: Evidence) -> str:
    return _digest([evidence.scope.provider, evidence.scope.timezone,
                    [_hour_content(row) for row in evidence.hours]])


def canonical_fingerprint(evidence: Evidence) -> str | None:
    """Hash only normalized hourly content/provider/zone; malformed input => None.

    All supplied coverage participates, including undisplayed hours. IDs, source
    times, daily totals, rank, text, and arbitrary JSON fields do not participate.
    Null metrics outside W remain explicit unknowns, never become zero.
    """
    try:
        return _fingerprint(_normalize(evidence))
    except (ValueError, TypeError, AttributeError, OverflowError, ArithmeticError, KeyError, OSError):
        return None


def _strong(row: Hour) -> bool:
    return row.probability >= 70 or row.rainfall_mm >= 10


def _increase(baseline: Hour, candidate: Hour) -> bool:
    # Exact rational subtraction avoids Decimal context rounding at thresholds.
    return (Fraction(candidate.probability) - Fraction(baseline.probability) >= 20
            or Fraction(candidate.rainfall_mm) - Fraction(baseline.rainfall_mm) >= 5)


def compare_intraday(baseline: Baseline | None, candidate: Evidence, *, now: datetime) -> Decision:
    """Return skip/suppress/notify, ordered reasons, frozen triggers and event ID.

    Approved constants: strong 70% OR 10 hourly mm; delta 20 pp OR 5 hourly mm;
    horizon 6h, minimum 2h; source ages 90m/24h, delivery age 24h; cooldown 3h;
    earlier onset >=2h and candidate lead <=4h. No production activation.
    Same source ID with changed content is inconsistent replay. Same-ID exact
    replay may suppress at equal retrieval; all other retrievals must be newer.
    No historical replay ledger is maintained or queried by this function.
    """
    try:
        return _compare(baseline, candidate, _utc(now))
    except (ValueError, TypeError, AttributeError, OverflowError, ArithmeticError, KeyError, OSError):
        return Decision("skip", ("malformed_input",))


def _compare(baseline: Baseline | None, candidate: Evidence, now: datetime) -> Decision:
    if baseline is None:
        return Decision("skip", ("no_baseline",))
    if not isinstance(baseline, Baseline):
        return Decision("skip", ("malformed_input",))
    if baseline.evidence is None:
        return Decision("skip", ("unknown_baseline",))
    if not isinstance(baseline.evidence, Evidence) or baseline.evidence.schema_version != 1:
        return Decision("skip", ("unsupported_baseline",))
    if not _identifier(baseline.delivery_id):
        return Decision("skip", ("malformed_input",))
    previous, current = _normalize(baseline.evidence), _normalize(candidate)
    accepted = _utc(baseline.accepted_at)
    if previous.scope != current.scope:
        return Decision("skip", ("scope_mismatch",))
    if any(value > now for value in (accepted, previous.retrieved_at, current.retrieved_at)):
        return Decision("skip", ("future_timestamp",))
    if now - accepted > timedelta(hours=24) or now - previous.retrieved_at > timedelta(hours=24):
        return Decision("skip", ("stale_baseline",))
    if now - current.retrieved_at > timedelta(minutes=90):
        return Decision("skip", ("stale_candidate",))
    if previous.model_time is not None and current.model_time is not None and current.model_time < previous.model_time:
        return Decision("skip", ("model_regression",))

    # Infer only the hourly phase, never the available overlap or row count.
    # This also supports providers whose UTC intervals start at :30 or :45.
    anchor = next((row.start for row in current.hours if row.start >= now), now)
    phase = anchor - anchor.replace(minute=0, second=0, microsecond=0)
    start = now.replace(minute=0, second=0, microsecond=0) + phase
    if start < now:
        start += HOUR
    zone = ZoneInfo(current.scope.timezone)
    today = now.astimezone(zone).date()
    window = []
    while start + HOUR <= now + timedelta(hours=6):
        if start.astimezone(zone).date() == today:
            window.append((start, start + HOUR))
        start += HOUR
    window = tuple(window)
    if len(window) < 2:
        return Decision("skip", ("short_window",), window)
    old = {(row.start, row.end): row for row in previous.hours}
    new = {(row.start, row.end): row for row in current.hours}
    for rows in (old, new):
        if any(key not in window and key[0] >= now and key[1] <= now + 6 * HOUR
               and key[0].astimezone(zone).date() == today for key in rows):
            return Decision("skip", ("incomplete_coverage",), window)
    for key in window:
        for rows in (old, new):
            if key not in rows or rows[key].probability is None or rows[key].rainfall_mm is None:
                return Decision("skip", ("incomplete_coverage",), window)

    fingerprint = _fingerprint(current)
    identical = fingerprint == _fingerprint(previous)
    if previous.source_id == current.source_id and not identical:
        return Decision("skip", ("inconsistent_replay",), window, candidate_fingerprint=fingerprint)
    if current.retrieved_at < previous.retrieved_at or (
        current.retrieved_at == previous.retrieved_at and previous.source_id != current.source_id
    ):
        return Decision("skip", ("source_not_newer",), window, candidate_fingerprint=fingerprint)
    if identical:
        return Decision("suppress", ("identical_content",), window, candidate_fingerprint=fingerprint)
    if current.retrieved_at == previous.retrieved_at:
        return Decision("skip", ("source_not_newer",), window, candidate_fingerprint=fingerprint)

    old_strong = [key for key in window if _strong(old[key])]
    new_strong = [key for key in window if _strong(new[key])]
    triggers = []
    if old_strong and new_strong:
        onset = new_strong[0]
        if old_strong[0][0] - onset[0] >= 2 * HOUR and onset[0] - now <= 4 * HOUR and not _strong(old[onset]):
            triggers.append(Trigger("earlier_onset", old[onset], new[onset]))
    if not old_strong:
        triggers.extend(Trigger("new_rain", old[key], new[key]) for key in new_strong if _increase(old[key], new[key]))
    triggers.extend(Trigger("escalation", old[key], new[key]) for key in new_strong if _increase(old[key], new[key]))
    if not triggers:
        return Decision("suppress", ("no_significant_change",), window, candidate_fingerprint=fingerprint)
    triggers = tuple(triggers)
    reasons = tuple(dict.fromkeys(trigger.reason for trigger in triggers))
    if now - accepted < 3 * HOUR:
        return Decision("suppress", ("cooldown",), window, triggers, fingerprint)
    event = _digest([baseline.delivery_id, POLICY_VERSION,
                     [[trigger.reason, _hour_content(trigger.baseline), _hour_content(trigger.candidate)]
                      for trigger in triggers]])
    return Decision("notify", reasons, window, triggers, fingerprint, event)
