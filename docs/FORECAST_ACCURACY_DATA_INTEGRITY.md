# Forecast Accuracy Data Integrity

## Purpose

Establish a trustworthy production data pipeline before using accuracy metrics to judge or tune the forecast system.

The required chain is:

```
Forecast Snapshot
    -> Forecast target time
    -> Actual Observation
    -> Deterministic matching
    -> Evaluation
    -> Accuracy metrics
```

Do not claim forecast accuracy until the underlying snapshot/observation pairs pass the integrity checks below.

## P0 — Production data integrity

### Forecast Snapshot

- [ ] Verify the scheduled snapshot is created on every expected run.
- [ ] Verify `snapshot_created_at` is populated and has consistent timezone semantics.
- [ ] Verify `forecast_target_time` is correct.
- [ ] Verify latitude/longitude identify the intended forecast location.
- [ ] Verify the administrative area/location binding is correct.
- [ ] Verify provider/model identity is stored.
- [ ] Verify required forecast fields are populated.
- [ ] Detect unintended duplicate snapshots for the same location + target time + forecast run identity.
- [ ] Confirm snapshots are immutable historical records and are not overwritten by later forecasts.

### Actual Observation

- [ ] Verify observations are created for every expected completed target time.
- [ ] Verify `observed_at` is correct and timezone semantics are consistent.
- [ ] Verify observation location matches the intended forecast location.
- [ ] Verify required observed values are populated or explicitly marked missing.
- [ ] Detect duplicate observations for the same location + observation time.
- [ ] Confirm observations do not contain future data relative to their collection timestamp.
- [ ] Verify the observation source is the expected source.

### Forecast ↔ Observation matching

- [ ] Match by location identity/coordinates and target observation time, not by calendar date alone.
- [ ] Define and document the allowed time tolerance/window.
- [ ] Verify UTC vs Asia/Bangkok conversion does not shift the target by 7 hours.
- [ ] Ensure one forecast target cannot silently match multiple observations.
- [ ] Detect unmatched forecasts.
- [ ] Detect observations with no corresponding forecast.
- [ ] Detect time mismatches outside the allowed tolerance.
- [ ] Detect location mismatches.
- [ ] Record a deterministic evaluation status such as `PENDING`, `MATCHED`, `EVALUATED`, `MISSING_OBSERVATION`, `TIME_MISMATCH`, `LOCATION_MISMATCH`, `DUPLICATE`, or `INVALID_DATA`.

## P0 — Daily read-only verification

Run a production read-only check and record:

- [ ] Expected vs actual Forecast Snapshot count.
- [ ] Expected vs actual Observation count.
- [ ] Earliest/latest snapshot timestamps.
- [ ] Earliest/latest observation timestamps.
- [ ] Number of matched pairs.
- [ ] Number of missing observations.
- [ ] Number of unmatched observations.
- [ ] Number of time mismatches.
- [ ] Number of location mismatches.
- [ ] Number of duplicates.
- [ ] Number of invalid/null required values.
- [ ] Number of evaluated pairs.

Minimum acceptance condition:

```
No unexplained missing pairs
+ No unintended duplicates
+ No unexplained time/location mismatches
+ Correct timezone semantics
= Accuracy data is eligible for evaluation
```

## P1 — Accuracy evaluation

Only after P0 integrity passes:

- [ ] Calculate rain occurrence accuracy (rain/no-rain).
- [ ] Evaluate probability calibration for forecast precipitation probability.
- [ ] Calculate temperature error metrics (for example MAE).
- [ ] Calculate precipitation amount error metrics.
- [ ] Separate metrics by forecast horizon.
- [ ] Separate metrics by location.
- [ ] Separate metrics by provider/model.
- [ ] Keep sample counts with every metric.
- [ ] Do not report a percentage without the evaluation sample size.

## P2 — Forecast improvement

After enough validated production data has accumulated:

- [ ] Identify systematic forecast errors.
- [ ] Compare providers/models using the same held-out observations.
- [ ] Evaluate local probability calibration.
- [ ] Evaluate local temperature bias correction.
- [ ] Re-run evaluation after each change.
- [ ] Keep a before/after record so improvements are evidence-based.
- [ ] Avoid tuning against future/held-out observations.

## Daily report target

The operational report should be able to answer:

```
WEATHER DATA INTEGRITY — YYYY-MM-DD

Forecast snapshots: expected / actual
Observations:        expected / actual

Matched:             N
Missing:             N
Unmatched:           N
Time mismatch:       N
Location mismatch:   N
Duplicates:          N
Invalid data:        N

Evaluation eligible: YES / NO
Reason: ...
```

## Current priority

**Do not add major accuracy-dependent product claims or decision features yet.**

First make the production chain reliable:

```
collect -> match -> validate -> evaluate -> analyze -> improve -> re-evaluate
```

The objective is not to assume that the system is accurate. The objective is to produce enough trustworthy evidence to determine how accurate it actually is.
