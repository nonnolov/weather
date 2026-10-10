"""Explicitly selected candidate policy; no scheduler or sender imports.

Retains v1 data-quality, source-order, scope and day-window gates.
The existing 70%/10 mm thresholds are reused, not meteorological severity labels.
A <=2h urgent horizon is provisional and must be evaluated against observations.
Delivery must explicitly select this policy and version its frozen evidence;
v1 remains the default in production callers.
"""
from datetime import timedelta
from fractions import Fraction

from app.notifications.intraday_comparison import (
    Baseline, Decision, Evidence, Trigger, _digest, _hour_content, _increase,
    _normalize, _strong, _utc, compare_intraday,
)

CANDIDATE_POLICY_VERSION = "intraday-v2-candidate"
URGENT_HORIZON = timedelta(hours=2)


def compare_candidate_policy(baseline: Baseline | None, candidate: Evidence, *, now) -> Decision:
    """Pure decision function; never call the live sender directly.

    Crossing either existing threshold is significant even below v1 deltas.
    Earlier onset of >=1h is significant only when onset is <=2h away;
    the original >=2h/<=4h rule remains for other earlier-onset changes.
    Within the 3h cooldown, only imminent threshold crossings, earlier onset,
    or >=5 mm hourly escalation bypass suppression. Probability-only increases
    in an already qualifying hour do not bypass cooldown.
    """
    original = compare_intraday(baseline, candidate, now=now)
    if original.outcome == "skip" or original.reasons == ("identical_content",):
        return original
    # Successful v1 validation guarantees a known, normalized baseline/window.
    previous, current = _normalize(baseline.evidence), _normalize(candidate)
    now = _utc(now)
    old = {(row.start, row.end): row for row in previous.hours}
    new = {(row.start, row.end): row for row in current.hours}
    old_strong = [key for key in original.window if _strong(old[key])]
    new_strong = [key for key in original.window if _strong(new[key])]
    triggers = []
    urgent = False
    if old_strong and new_strong:
        onset = new_strong[0]
        advance = old_strong[0][0] - onset[0]
        lead = onset[0] - now
        if not _strong(old[onset]) and (
            (advance >= timedelta(hours=2) and lead <= timedelta(hours=4))
            or (advance >= timedelta(hours=1) and lead <= URGENT_HORIZON)
        ):
            triggers.append(Trigger("earlier_onset", old[onset], new[onset]))
            urgent = lead <= URGENT_HORIZON
    for key in new_strong:
        before, after = old[key], new[key]
        crossed = (before.probability < 70 <= after.probability
                   or before.rainfall_mm < 10 <= after.rainfall_mm)
        increased = _increase(before, after)
        if not crossed and not increased:
            continue
        reason = "new_rain" if not _strong(before) else "escalation"
        triggers.append(Trigger(reason, before, after))
        rain_increase = Fraction(after.rainfall_mm) - Fraction(before.rainfall_mm) >= 5
        if after.start - now <= URGENT_HORIZON and (crossed or rain_increase):
            urgent = True
    if not triggers:
        return Decision("suppress", ("no_significant_change",), original.window,
                        candidate_fingerprint=original.candidate_fingerprint)
    triggers = tuple(triggers)
    if now - _utc(baseline.accepted_at) < timedelta(hours=3) and not urgent:
        return Decision("suppress", ("cooldown",), original.window, triggers,
                        original.candidate_fingerprint)
    reasons = tuple(dict.fromkeys(item.reason for item in triggers))
    event = _digest([baseline.delivery_id, CANDIDATE_POLICY_VERSION,
                     [[item.reason, _hour_content(item.baseline), _hour_content(item.candidate)]
                      for item in triggers]])
    return Decision("notify", reasons, original.window, triggers,
                    original.candidate_fingerprint, event)
