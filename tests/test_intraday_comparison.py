"""Fixed-clock synthetic pure comparison tests; no DB or delivery fixtures."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.notifications.intraday_comparison import (
    Baseline, Evidence, Hour, Scope, canonical_fingerprint, compare_intraday,
)


NOW = datetime(2026, 10, 10, 3, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
SCOPE = Scope("U_TEST", 101, "open_meteo", "Asia/Bangkok")


def evidence(*, probability=10, mm=0, source="candidate", retrieved=None, now=NOW):
    return Evidence(
        SCOPE, source, retrieved or now - timedelta(minutes=30),
        tuple(Hour(now + index * HOUR, now + (index + 1) * HOUR, probability, mm)
              for index in range(6)),
    )


def baseline(*, probability=10, mm=0, now=NOW):
    return Baseline("delivery-1", now - 4 * HOUR,
                    evidence(probability=probability, mm=mm, source="baseline",
                             retrieved=now - 4 * HOUR, now=now))


def change(record, index=0, **values):
    rows = list(record.hours)
    rows[index] = replace(rows[index], **values)
    return replace(record, hours=tuple(rows))


def assert_decision(old, new, outcome, reason, *, now=NOW):
    result = compare_intraday(old, new, now=now)
    assert result.outcome == outcome
    assert reason in result.reasons
    return result


@pytest.mark.parametrize("metric,old,value,outcome", [
    ("probability", 70, 89.99, "suppress"),
    ("probability", 70, 90, "notify"),
    ("probability", 70, 90.01, "notify"),
    ("probability", 70, Decimal("89.999999999999999999999999999999"), "suppress"),
    ("rainfall_mm", 10, 14.99, "suppress"),
    ("rainfall_mm", 10, 15, "notify"),
    ("rainfall_mm", 10, 15.01, "notify"),
    ("rainfall_mm", 10, Decimal("14.999999999999999999999999999999"), "suppress"),
])
def test_inclusive_delta(metric, old, value, outcome):
    previous = baseline(probability=old) if metric == "probability" else baseline(mm=old)
    candidate = evidence(probability=old) if metric == "probability" else evidence(mm=old)
    result = compare_intraday(previous, change(candidate, **{metric: value}), now=NOW)
    assert result.outcome == outcome
    assert result.reasons == (("escalation",) if outcome == "notify" else ("no_significant_change",))


@pytest.mark.parametrize("old_probability,old_mm,new_probability,new_mm,outcome", [
    (69, 0, 70, 0, "suppress"), (0, 9.9, 0, 10, "suppress"),
    (29, 0, 49, 0, "suppress"), (30, 0, 50, 0, "suppress"),
    (0, 0, 0, 5, "suppress"), (10, 0, 69.99, 0, "suppress"),
    (10, 0, 70, 0, "notify"), (35, 0, 70, 0, "notify"),
    (0, 0, 0, 9.99, "suppress"), (0, 5, 0, 10, "notify"),
    (90, 15, 50, 0, "suppress"), (90, 15, 0, 0, "suppress"),
])
def test_strong_crossing_fallback_new_and_weakening(old_probability, old_mm, new_probability, new_mm, outcome):
    result = compare_intraday(baseline(probability=old_probability, mm=old_mm),
                              evidence(probability=new_probability, mm=new_mm), now=NOW)
    assert result.outcome == outcome
    if outcome == "notify":
        assert result.reasons == ("new_rain", "escalation")


@pytest.mark.parametrize("candidate_index,outcome", [(2, "suppress"), (1, "notify"), (0, "notify")])
def test_earlier_onset_without_magnitude_change(candidate_index, outcome):
    old = baseline(probability=69)
    old = replace(old, evidence=change(old.evidence, 3, probability=70))
    new = change(evidence(probability=69), 3, probability=70)
    result = compare_intraday(old, change(new, candidate_index, probability=70), now=NOW)
    assert result.outcome == outcome
    if outcome == "notify":
        assert result.reasons == ("earlier_onset",)
        assert result.triggers[0].candidate.start == NOW + candidate_index * HOUR


def test_earlier_and_escalation_order_one_decision():
    old = baseline(probability=69)
    old = replace(old, evidence=change(old.evidence, 3, probability=70))
    new = change(change(evidence(probability=69), 3, probability=90), 1, probability=70)
    result = assert_decision(old, new, "notify", "earlier_onset")
    assert result.reasons == ("earlier_onset", "escalation")
    assert [item.reason for item in result.triggers] == ["earlier_onset", "escalation"]


def test_additional_window_crossing_later_shift_and_third_window():
    old = baseline(probability=69)
    old = replace(old, evidence=change(change(old.evidence, 0, probability=70), 2, probability=80))
    new = replace(old.evidence, source_id="candidate", retrieved_at=NOW - timedelta(minutes=30))
    assert_decision(old, change(new, 4, probability=70), "suppress", "no_significant_change")
    shifted = change(change(new, 0, probability=69), 1, probability=70)
    assert_decision(old, shifted, "suppress", "no_significant_change")
    result = assert_decision(old, change(new, 4, probability=90), "notify", "escalation")
    assert len(result.triggers) == 1
    assert result.triggers[0].candidate.start == NOW + 4 * HOUR


def test_rank_order_only_and_identical_different_ids():
    old = baseline(probability=70)
    new = replace(old.evidence, source_id="new-id", retrieved_at=NOW - timedelta(minutes=30),
                  hours=tuple(reversed(old.evidence.hours)))
    assert_decision(old, new, "suppress", "identical_content")


def test_same_id_exact_replay_and_mutated_content():
    old = baseline()
    old = replace(old, accepted_at=NOW - HOUR,
                  evidence=replace(old.evidence, retrieved_at=NOW - HOUR))
    assert_decision(old, old.evidence, "suppress", "identical_content")
    assert_decision(old, change(old.evidence, probability=70), "skip", "inconsistent_replay")
    newer_mutation = replace(change(old.evidence, probability=70), retrieved_at=NOW - timedelta(minutes=30))
    assert_decision(old, newer_mutation, "skip", "inconsistent_replay")


@pytest.mark.parametrize("age,outcome", [
    (timedelta(hours=3, seconds=-1), "suppress"),
    (timedelta(hours=3), "notify"), (timedelta(hours=3, seconds=1), "notify"),
])
def test_cooldown_inclusive_no_new_rain_exception(age, outcome):
    old = replace(baseline(), accepted_at=NOW - age)
    result = compare_intraday(old, change(evidence(), probability=70), now=NOW)
    assert result.outcome == outcome
    assert ("cooldown" in result.reasons) == (outcome == "suppress")
    assert (result.event_id is None) == (outcome == "suppress")


def test_cooldown_no_earlier_onset_exception():
    old = baseline(probability=69)
    old = replace(old, accepted_at=NOW - 2 * HOUR, evidence=change(old.evidence, 3, probability=70))
    new = change(change(evidence(probability=69), 3, probability=70), 0, probability=70)
    assert_decision(old, new, "suppress", "cooldown")


@pytest.mark.parametrize("seconds,outcome", [(5401, "skip"), (5400, "notify"), (5399, "notify"), (0, "notify"), (-1, "skip")])
def test_candidate_age_boundary(seconds, outcome):
    new = replace(change(evidence(), probability=70), retrieved_at=NOW - timedelta(seconds=seconds))
    result = compare_intraday(baseline(), new, now=NOW)
    assert result.outcome == outcome
    if outcome == "skip":
        assert result.reasons == (("future_timestamp",) if seconds < 0 else ("stale_candidate",))


@pytest.mark.parametrize("field", ["accepted_at", "retrieved_at"])
@pytest.mark.parametrize("seconds,outcome", [(86399, "notify"), (86400, "notify"), (86401, "skip"), (-1, "skip")])
def test_baseline_age_boundaries(field, seconds, outcome):
    old = baseline()
    if field == "accepted_at":
        old = replace(old, accepted_at=NOW - timedelta(seconds=seconds))
    else:
        old = replace(old, evidence=replace(old.evidence, retrieved_at=NOW - timedelta(seconds=seconds)))
    result = compare_intraday(old, change(evidence(), probability=70), now=NOW)
    assert result.outcome == outcome
    if outcome == "skip":
        assert result.reasons == (("future_timestamp",) if seconds < 0 else ("stale_baseline",))


@pytest.mark.parametrize("old,reason", [
    (None, "no_baseline"), (Baseline("d", NOW - 4 * HOUR, None), "unknown_baseline"),
    (replace(baseline(), evidence=replace(baseline().evidence, schema_version=2)), "unsupported_baseline"),
    (replace(baseline(), evidence={}), "unsupported_baseline"),
])
def test_no_null_legacy_unsupported_baseline(old, reason):
    assert_decision(old, change(evidence(), probability=70), "skip", reason)


@pytest.mark.parametrize("retrieved", [NOW - timedelta(minutes=30), NOW - HOUR])
def test_equal_or_older_source_not_newer(retrieved):
    # Fresh candidate and baseline ensure source order, rather than age, decides.
    old = replace(baseline(), accepted_at=NOW - timedelta(minutes=15),
                  evidence=replace(baseline().evidence, retrieved_at=NOW - timedelta(minutes=30)))
    new = replace(change(evidence(), probability=70), retrieved_at=retrieved)
    assert_decision(old, new, "skip", "source_not_newer")


@pytest.mark.parametrize("old_model,new_model,outcome", [
    (NOW - 2 * HOUR, NOW - 3 * HOUR, "skip"),
    (NOW - 2 * HOUR, NOW - 2 * HOUR, "notify"),
    (NOW - 2 * HOUR, NOW - HOUR, "notify"),
    (None, NOW - 3 * HOUR, "notify"), (NOW - 2 * HOUR, None, "notify"),
])
def test_model_regression_only_when_both_known(old_model, new_model, outcome):
    old = replace(baseline(), evidence=replace(baseline().evidence, model_time=old_model))
    new = replace(change(evidence(), probability=70), model_time=new_model)
    result = compare_intraday(old, new, now=NOW)
    assert result.outcome == outcome
    if outcome == "skip":
        assert result.reasons == ("model_regression",)


@pytest.mark.parametrize("side", ["candidate", "baseline"])
@pytest.mark.parametrize("metric,value", [
    ("probability", None), ("rainfall_mm", None),
    ("probability", float("nan")), ("probability", float("inf")),
    ("rainfall_mm", float("nan")), ("rainfall_mm", float("inf")),
    ("rainfall_mm", -0.01), ("probability", -0.01), ("probability", 100.01),
    ("probability", True), ("rainfall_mm", "5"),
])
def test_invalid_or_null_metrics(side, metric, value):
    old, new = baseline(), change(evidence(), probability=70)
    if side == "candidate":
        new = change(new, 5, **{metric: value})
    else:
        old = replace(old, evidence=change(old.evidence, 5, **{metric: value}))
    assert_decision(old, new, "skip", "incomplete_coverage" if value is None else "malformed_input")


@pytest.mark.parametrize("side", ["candidate", "baseline"])
@pytest.mark.parametrize("fault", ["missing", "duplicate", "duration", "shifted", "reversed"])
def test_interval_quality_and_exact_coverage(side, fault):
    old, new = baseline(), change(evidence(), probability=70)
    record = new if side == "candidate" else old.evidence
    if fault == "missing":
        record = replace(record, hours=record.hours[:-1])
    elif fault == "duplicate":
        record = replace(record, hours=record.hours + (record.hours[0],))
    elif fault == "duration":
        record = change(record, 5, end=record.hours[5].end + timedelta(minutes=1))
    elif fault == "shifted":
        record = change(record, 5, start=record.hours[5].start + timedelta(minutes=30),
                        end=record.hours[5].end + timedelta(minutes=30))
    else:
        record = change(record, 5, start=record.hours[5].end, end=record.hours[5].start)
    if side == "candidate":
        new = record
    else:
        old = replace(old, evidence=record)
    assert_decision(old, new, "skip", "incomplete_coverage" if fault in ("missing", "shifted") else "malformed_input")


def test_sparse_unknown_outside_window_allowed_and_elapsed_underway_excluded():
    extra = (Hour(NOW - HOUR, NOW, 100, 20),
             Hour(NOW - timedelta(minutes=30), NOW + timedelta(minutes=30), 100, 20),
             Hour(NOW + 7 * HOUR, NOW + 8 * HOUR, None, None))
    old = baseline()
    old = replace(old, evidence=replace(old.evidence, hours=extra + old.evidence.hours))
    new = replace(evidence(), hours=extra + evidence().hours)
    assert_decision(old, new, "suppress", "identical_content")
    result = assert_decision(old, change(new, 3, probability=70), "notify", "new_rain")
    assert result.window[0] == (NOW, NOW + HOUR)
    assert len(result.window) == 6


def test_non_hour_clock_requires_all_five_remaining_whole_hours():
    clock = NOW + timedelta(minutes=30)
    result = assert_decision(baseline(), change(evidence(), 1, probability=70), "notify", "new_rain", now=clock)
    assert len(result.window) == 5
    assert result.window[0][0] == NOW + HOUR
    missing = replace(evidence(), hours=evidence().hours[:-1])
    assert_decision(baseline(), missing, "skip", "incomplete_coverage", now=clock)


@pytest.mark.parametrize("hour,outcome", [(15, "notify"), (16, "skip")])
def test_local_midnight_start_membership_and_minimum(hour, outcome):
    clock = NOW.replace(hour=hour)
    result = compare_intraday(baseline(now=clock), change(evidence(now=clock), probability=70), now=clock)
    assert result.outcome == outcome
    assert len(result.window) == (2 if hour == 15 else 1)
    assert result.window[-1][1] == clock.replace(hour=17)
    if outcome == "skip":
        assert result.reasons == ("short_window",)


def test_day_rollover_does_not_invent_baseline_or_reset_cooldown():
    clock = NOW.replace(hour=17)
    old = baseline(now=clock)
    old = replace(old, evidence=replace(old.evidence, hours=baseline(now=clock - 6 * HOUR).evidence.hours))
    assert_decision(old, change(evidence(now=clock), probability=70), "skip", "incomplete_coverage", now=clock)
    old = replace(baseline(now=clock), accepted_at=clock - 2 * HOUR)
    assert_decision(old, change(evidence(now=clock), probability=70), "suppress", "cooldown", now=clock)


@pytest.mark.parametrize("field,value,reason", [
    ("recipient_id", "U_OTHER", "scope_mismatch"), ("location_id", 102, "scope_mismatch"),
    ("provider", "other", "scope_mismatch"), ("timezone", "UTC", "scope_mismatch"),
    ("timezone", "Invalid/Zone", "malformed_input"), ("timezone", "", "malformed_input"),
    ("channel", "email", "malformed_input"), ("location_id", None, "malformed_input"),
])
def test_scope_and_invalid_timezone(field, value, reason):
    new = replace(change(evidence(), probability=70), scope=replace(SCOPE, **{field: value}))
    assert_decision(baseline(), new, "skip", reason)


def test_naive_and_offset_utc_normalization_and_input_immutability():
    old, new = baseline(), change(evidence(), probability=70)
    original = (old, new)
    expected = compare_intraday(old, new, now=NOW)
    offset = timezone(timedelta(hours=7))
    adjusted = replace(new, retrieved_at=new.retrieved_at.astimezone(offset),
                       hours=tuple(replace(row, start=row.start.astimezone(offset), end=row.end.astimezone(offset))
                                   for row in new.hours))
    naive_old = replace(old, accepted_at=old.accepted_at.replace(tzinfo=None),
                        evidence=replace(old.evidence, retrieved_at=old.evidence.retrieved_at.replace(tzinfo=None),
                                         hours=tuple(replace(row, start=row.start.replace(tzinfo=None), end=row.end.replace(tzinfo=None))
                                                     for row in old.evidence.hours)))
    assert compare_intraday(naive_old, adjusted, now=NOW.replace(tzinfo=None)) == expected
    assert (old, new) == original
    with pytest.raises(FrozenInstanceError):
        expected.triggers[0].candidate.probability = 0


def test_canonical_numbers_provider_order_and_event_identity():
    old, new = baseline(), change(evidence(), probability=70)
    expected = compare_intraday(old, new, now=NOW)
    variant = replace(new, source_id=999, retrieved_at=NOW - timedelta(minutes=15),
                      scope=replace(SCOPE, provider=" OPEN_METEO ", timezone=" Asia/Bangkok "),
                      hours=tuple(replace(row, probability=Decimal(str(row.probability) + ".000"), rainfall_mm=-0.0)
                                  for row in reversed(new.hours)))
    result = compare_intraday(old, variant, now=NOW)
    assert result.candidate_fingerprint == expected.candidate_fingerprint
    assert result.event_id == expected.event_id
    assert canonical_fingerprint(new) == canonical_fingerprint(variant)
    other_baseline = compare_intraday(replace(old, delivery_id="delivery-2"), new, now=NOW)
    assert other_baseline.event_id != expected.event_id
    changed = compare_intraday(old, change(new, probability=71), now=NOW)
    assert changed.event_id != expected.event_id
    assert canonical_fingerprint(change(new, 5, probability=11)) != canonical_fingerprint(new)
    unrelated = compare_intraday(old, change(new, 5, probability=11), now=NOW)
    assert unrelated.event_id == expected.event_id


@pytest.mark.parametrize("candidate", [None, {}, replace(evidence(), hours=[]),
                                       replace(evidence(), retrieved_at=None),
                                       replace(evidence(), source_id=None),
                                       replace(evidence(), schema_version=2)])
def test_malformed_public_input_deterministic(candidate):
    assert_decision(baseline(), candidate, "skip", "malformed_input")
    assert canonical_fingerprint(candidate) is None


def test_invalid_clock_returns_skip():
    assert compare_intraday(baseline(), evidence(), now=None).reasons == ("malformed_input",)


@pytest.mark.parametrize("index", [4, 5])
def test_onset_at_or_beyond_four_hours_without_two_hour_advance(index):
    # In a six-hour W, >=2h advance implies lead <=3h on this hourly grid.
    # A lead beyond 4h cannot independently satisfy the earlier-onset rule.
    old = baseline(probability=69)
    old = replace(old, evidence=change(old.evidence, 5, probability=70))
    new = change(change(evidence(probability=69), 5, probability=70), index, probability=70)
    reason = "identical_content" if index == 5 else "no_significant_change"
    assert_decision(old, new, "suppress", reason)


def test_fingerprint_ignores_source_and_model_metadata_but_not_zone_provider():
    original = evidence()
    metadata = replace(original, source_id="other", retrieved_at=NOW,
                       model_time=NOW - HOUR)
    assert canonical_fingerprint(metadata) == canonical_fingerprint(original)
    for scope in (replace(SCOPE, provider="other"), replace(SCOPE, timezone="UTC")):
        assert canonical_fingerprint(replace(original, scope=scope)) != canonical_fingerprint(original)


def test_baseline_unknown_metrics_outside_window_do_not_invent_absence():
    old = baseline()
    outside = Hour(NOW - HOUR, NOW, None, None)
    old = replace(old, evidence=replace(old.evidence, hours=(outside,) + old.evidence.hours))
    assert_decision(old, change(evidence(), probability=70), "notify", "new_rain")


def test_nonzero_hourly_phase_and_missing_leading_row_cannot_shrink_window():
    offset = timedelta(minutes=30)
    old, new = baseline(), change(evidence(), 1, probability=70)
    def shifted(record):
        return replace(record, hours=tuple(replace(row, start=row.start + offset, end=row.end + offset)
                                           for row in record.hours))
    old = replace(old, evidence=shifted(old.evidence))
    new = shifted(new)
    result = assert_decision(old, new, "notify", "new_rain")
    assert len(result.window) == 5
    assert result.window[0] == (NOW + offset, NOW + offset + HOUR)
    missing = replace(new, hours=new.hours[1:])
    result = assert_decision(old, missing, "skip", "incomplete_coverage")
    assert len(result.window) == 5
    assert result.window[0][0] == NOW + offset


def test_overlapping_future_hourly_phases_are_not_ignored():
    new = change(evidence(), probability=70)
    overlap = Hour(NOW + timedelta(minutes=30), NOW + timedelta(minutes=90), 100, 20)
    new = replace(new, hours=new.hours + (overlap,))
    assert_decision(baseline(), new, "skip", "incomplete_coverage")


def test_missing_leading_trailing_or_all_rows_preserves_full_window():
    for rows in (evidence().hours[1:], evidence().hours[:-1], ()):
        new = replace(change(evidence(), probability=70), hours=rows)
        result = assert_decision(baseline(), new, "skip", "incomplete_coverage")
        assert len(result.window) == 6


def test_elapsed_and_underway_changes_cannot_trigger():
    new = evidence()
    outside = (Hour(NOW - HOUR, NOW, 100, 100),
               Hour(NOW - timedelta(minutes=30), NOW + timedelta(minutes=30), 100, 100))
    new = replace(new, hours=outside + new.hours)
    result = assert_decision(baseline(), new, "suppress", "no_significant_change")
    assert not result.triggers
