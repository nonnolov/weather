# P2-01: forecast evaluation integrity

## Dependencies and scope

User authorized beginning P2 after reviewing P1. Current baseline is review commit fa80ebcfec47a472754f2005450058efa8e4dfbc; production remains the successful P1-14 API deployment. P1's natural positive LINE acceptance remains an open gate independent of this evaluation task.

Scope: a read-only audited evaluation for temperature and total hourly precipitation, archive request isolation, two concrete legacy evaluation fixes, tests, current roadmap clarification, and sanitized production/reference evidence. No new database schema, scheduler, LINE policy, station collector, correction activation or production deployment is part of this package.

## Changes

- New GET /api/v1/forecast/{location_id}/evaluation/audit accepts days=1..90 (default 30) and optional timezone-aware historical as_of. Future or naive cutoff requests are rejected. Existing evaluation response shape is retained.
- Pair immutable snapshots with the exact location and reference end timestamp. Temperature is instantaneous. Open-Meteo hourly precipitation is an accumulation for the preceding hour: retrieval must be no later than the interval start, and the whole interval must fit inside the evaluation window.
- Require reference availability by the audit cutoff. Missing, invalid, unknown-provenance, misaligned or out-of-window pairs receive explicit exclusion reasons. Missing values never become zero.
- Group retrieval-based lead times into [0,3), [3,6), [6,12), [12,24), [24,48), [48,72), [72,168), [168,384) hours. Precipitation leads are measured to interval start; temperature leads to valid time. Unknown model initialization is not inferred from retrieval time.
- Select one latest retrieval per target/provider/reference/horizon bucket with deterministic run/row tie breaking. Other snapshots in that bucket do not inflate the count. The same target in different horizon buckets is explicitly evaluated at those different leads.
- Report MAE, RMSE, signed forecast-minus-reference bias, sample and unique-target counts. Total precipitation occurrence uses >0.1 mm; report hits, misses, false alarms, correct dry, precision, recall, false-alarm ratio and Brier score for valid forecast probabilities. Undefined ratios and unavailable Brier scores are null.
- Archive references from open_meteo_historical are always labeled reanalysis. Unknown station/manual source strings are excluded rather than presumed verified. Results never claim verified at-point accuracy or evaluate notifier delivery/cooldown. Total precipitation includes precipitation types; it is not a calibrated local rain-severity category.
- Fix legacy populated metric serialization via Pydantic from_attributes. Existing tests previously only exercised the empty API result; a nonempty response exposed the defect.
- Reject a negative subsecond forecast horizon before rounding, preventing a just-past target from becoming a zero-lead sample.
- Separate observation archive fields from live forecast fields. Live forecast probability, visibility and UV requests remain unchanged. Archive now requests the documented fields needed by the observation store, retaining unavailable values as null.

## Acceptance checks

1. Cross-location, wrong-time, post-period retrieval, future/unavailable reference, invalid numbers and unknown provenance cannot produce audited scores.
2. Duplicate snapshots and input order cannot alter selected targets; boundaries and timezones are tested.
3. Populated old and new API responses serialize; invalid API windows fail.
4. Empty or ineligible data reports no eligible pairs, never a fabricated accuracy percentage.
5. Report executes in a real disposable PostgreSQL READ ONLY transaction without inserts, updates or deletes.
6. Regression passes including P1 delivery tests; original worktree hashes/branch/HEAD/index are preserved.

## Evidence and results

Targeted validation: 56 passed, one existing python_multipart warning. Full regression result is appended after completion.

P2_01_PRODUCTION_AUDIT.json records a READ ONLY / REPEATABLE READ audit of the four public seed locations and the one current authorized location using the new evaluator in an ephemeral SSH Python process. Code was not installed into the production application. No database write or LINE call occurred. All five audited scopes had zero eligible/matched pairs in the 90-day window. The current location had nine forecast runs and zero observations. Production contained 1,224 archive rows in total, but their existence does not establish matching reference coverage for these forecast targets.

P2_01_ARCHIVE_CONTRACT.json records two bounded real public-seed archive requests for 2024-01-01. Both the previous shared request and the isolated request returned HTTP 200 and 24 hourly rows. Therefore this package does not claim that the previous request necessarily failed with HTTP 400. The check validates request/parse availability, not forecast accuracy or at-point rainfall.

## Risks, limitations and next work

Reanalysis may share modeling inputs with forecast data; even eligible proxy comparisons are not independent gauge validation. Nearby station data need interval alignment and quality/provenance checks before ingestion. No verified at-point reference adapter exists in this package; verified_at_point_pairs remains zero.

No numerical operational accuracy baseline exists for the current location. Do not interpret zero eligible pairs as zero error or tune thresholds/corrections from mocked fixtures. Legacy exact-lead metrics remain a compatibility endpoint; audited provenance and bucketed results are the evaluation path introduced here.

The existing temperature correction is unchanged. Its chronological row split still needs review for duplicate valid-time targets crossing train/test and observation-availability cutoff handling before P2 can claim independently verified improvement.

Next: obtain reference coverage for elapsed, historically forecasted location/intervals, review the existing ingestion retry/availability behavior, then establish a baseline and verify correction candidates on later held-out targets. The user-specified station/point approach remains relevant; no unverified station stream is silently promoted to truth.

## Primary provider references

- https://open-meteo.com/en/docs (hourly precipitation period, probability definition)
- https://open-meteo.com/en/docs/historical-weather-api (archive variables and reanalysis provenance)

## Completed regression and preservation

Full suite: `python weather-p112-tests.py -m "not integration" -q` in the private credential-isolated runner. Result: **537 passed, 18 external integration cases deselected, one existing python_multipart warning**, pytest 280.14 seconds, process exit 0. The new P2 coverage adds 44 cases to the 493-case baseline. Provider contract reads above were separate bounded public API checks, not these mocked regression cases.

`git diff --check` passed. The review branch/HEAD remain review/p1-intraday-20261010 / fa80ebcfec47a472754f2005450058efa8e4dfbc, with an empty index; this P2 package is not committed, pushed or deployed. All 34 protected dirty files in the original worktree retained their checkpoint hashes, original branch, HEAD and empty index. The disposable PostgreSQL instance is stopped and removed after testing.

The public archive check additionally confirms that the previous request's probability, visibility and UV arrays contained zero non-null values for the checked day; retained fields contained 24 usable rows. Neither request result provides independent at-point measurements.

Performance limit: the current audit loads candidate rows for a bounded window up to 90 days. Before large-history rollout, add bounded query/streaming behavior and verify its row coverage; do not silently truncate a report. Current read-only evidence covers small histories only. P2 remains in progress; P2-01 integrity implementation is complete.


## User-selected minimum P2 scope (2026-10-10, Asia/Bangkok)

The user selected three deliverables: (1) collect actual reference data matched to forecasts, (2) measure forecast errors including false rain predictions and missed rain, (3) report results with sample counts and limitations. Model changes, ML and correction activation are deferred; they are not acceptance requirements for this minimum package.

Current evidence: evaluation/report implementation is locally tested, but no eligible production pairs exist in the last audit. Reference collection remains incomplete. The nearby GOT001 evidence has measured provider amounts but its timezone and accumulation interval contract remain unverified; do not assign these rows to the user's location or insert them into the location-only Observation table. The at-point report template is empty. No observation is invented to satisfy acceptance.

Minimum acceptance: retain provenance and actual measurement scope; match immutable pre-period forecasts to aligned, elapsed reference intervals; report amount errors only for quantified measurements and occurrence errors only where the relevant interval was observed; keep missing coverage distinct from dry weather; show sample count, unique target count, period, lead bucket, exclusions and spatial/source limitations. Nearby station comparisons must be labeled as nearby station comparisons. Reanalysis comparisons must remain labeled as proxy comparisons. Empty data must report unavailable scores. Operational alert thresholds and LINE delivery are separate from occurrence scoring.

Next collection gate: verify the public station feed's timezone, hourly interval boundaries and missing/error semantics, then preserve its station scope for matching forecasts at that station. For current-point verification, collect genuine point reports; a momentary dry check cannot establish an entire dry hour. This scope update changes documentation only; existing P2-01 code/test results remain valid. No commit, push, deployment, LINE send or production insert occurred in this scope review.
