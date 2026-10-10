# Intraday candidate policy: offline review and evidence boundary

## Result

This is a candidate evaluation package, not a production policy rollout or
a declaration that P1 acceptance is complete. P1-12 remains active and unchanged.
No commit, push, deployment, LINE call, provider request or database write was
performed for this package. Production reads used short read-only transactions.

## Candidate changes

- Reuse the existing thresholds: probability >=70% OR precipitation >=10 mm/hour.
  These are project policy thresholds, not official meteorological severity labels.
- A crossing of either threshold is significant even when the change is below
  20 percentage points or 5 mm/hour. Existing significant increases remain eligible.
- Keep the ordinary three-hour cooldown. Permit a candidate bypass only when a
  trigger starts within two hours AND is a threshold crossing, qualifying earlier
  onset, or an hourly precipitation increase of at least 5 mm.
- Probability-only increases within an already qualifying hour do not bypass.
- Keep the existing earlier-onset rule (>=2h earlier, <=4h away). Additionally,
  allow >=1h earlier when the onset is <=2h away.
- There is no blanket exemption for daily summaries: an imminent qualifying
  change can bypass even when the last baseline was a daily summary, but an
  unchanged forecast cannot. This avoids rebroadcasting the summary.
- Reuse v1 scope, newest source, quality, baseline age, source age, model-order,
  same-day coverage and minimum-window gates. Missing evidence remains a skip.
- Candidate event IDs include intraday-v2-candidate. The module is imported
  only by the offline replay module; the live scheduler/delivery path still uses v1.

The two-hour urgency horizon is provisional, not optimized or calibrated.
Threshold crossings near the boundary can increase notification frequency;
do not declare this policy better without measuring this tradeoff.

## Files

- app/notifications/intraday_candidate_policy.py: pure candidate comparator.
- app/notifications/intraday_policy_replay.py: offline, no-send replay CLI.
- tests/test_intraday_candidate_policy.py: 32 candidate boundary/safety tests.
- tests/test_intraday_policy_replay.py: seven as-of/no-network/replay tests.
- docs/P1_13_POLICY_REPLAY.json: sanitized real-history replay summary.
- This handoff.

The formatter already displays probability and hourly precipitation separately;
the new candidate test verifies that probability alone is not labeled heavy rain.
There was no change to the daily formatter, cron, delivery locking, intent
persistence, recipient allowlist, or current live configuration.

## Recorded-history result

Seven actual stored forecast snapshots were read for the existing recipient's
location, from 2026-10-10 11:56:17 to 19:58:23 Bangkok (UTC values in JSON).
The retained accepted baseline was at 16:57:49 Bangkok. Consequently the replay
covers 14 reconstructed evaluation points AFTER that baseline, not eight hours
of actual scheduler runs. Points are spaced 15 minutes from baseline acceptance,
plus a final point at the last recorded retrieval.

Two separate comparisons were evaluated:

1. Fixed recorded baseline: neither policy advances the baseline.
2. Hypothetical immediate acceptance: each policy maintains its own simulated
   baseline and advances only on notify. These are not real accepted messages.

For each policy and each mode, all 14 points suppressed: nine identical_content,
five no_significant_change, zero notify. There were zero outcome disagreements.
There was no positive event to compare urgency handling in this real dataset.

Each point uses only snapshots whose retrieval time is <= evaluation time.
No future snapshot leaks into earlier decisions. Provider model refresh latency,
actual native tick timing, delivery failure, network latency, and pending intent
reconciliation are not simulated. A hypothetical notify is eligibility only.

A separate read-only audit of observations for this location returned zero rows.
The export contains no measured rain. Accuracy, missed rain, false alarms and
actual warning lead time were NOT measured. Forecast-history agreement alone
cannot establish those metrics. No forecasts or evidence were fabricated in
production to manufacture a positive outcome.

The sanitized raw export remains outside git in the local temporary evidence
checkpoint weather-p113-history.json; recipient IDs, coordinates, names,
tokens and connection strings were not exported. Input SHA-256 is in the summary.
The CLI requires this recorded input and fails on empty, potentially truncated,
reversed or over-seven-day windows.

## Validation

Final command, using the pre-existing isolated test runner that clears provider
and LINE credentials and blocks external sockets:

    python weather-p112-tests.py tests/test_intraday_candidate_policy.py tests/test_intraday_policy_replay.py tests/test_intraday_comparison.py -q

Result: 156 passed, one existing python_multipart warning, exit 0.
Includes 39 new tests and 117 existing pure comparator tests. No production
database, weather provider or LINE endpoint was used by these tests.
An initial invocation used a nonexistent formatter-test filename; replay-test
fixture import and missing provider field were corrected before the final pass.
No existing tests or tracked implementation files were edited.

Original workspace: all 34 protected hashes match; original HEAD, branch and
empty index preserved. Review HEAD remains c7fe95e1cc31c63cb689ade4b8d2d1ccbeabdfad
and its index is empty. Changes are six new files, not committed.

## Remaining gates before activation

- Collect paired, time-aligned measured rain with known provenance for this
  location. Model-derived historical weather must not silently be treated as
  independent station measurements.
- Evaluate weather events including wet/dry cases and urgent changes, not only
  no-change snapshots. Report alert volume, false alarms, missed events,
  lead-time distribution and missing-data coverage. Select thresholds using
  a separate validation period; do not tune and assess on the same examples.
- For a live integration, version frozen comparison evidence and the historical
  replay validator together. Keep old v1 deliveries readable and preserve event
  dedupe, scope locks and pending-intent blocking across policy changes.
  DO NOT freeze a candidate decision through the unchanged v1 evidence writer.
- Test the policy inside the existing locked delivery path using fake clients
  and isolated PostgreSQL, then prepare an explicit rollout with default-off
  activation and rollback. A change of policy must not reset pending intents.
- Observe a naturally qualifying real event with authorized LINE delivery.
  Distinguish API acceptance plus durable commit from handset receipt.
  There is no queued catch-up message for suppressed past forecasts.

These gates remain open. This package completes the offline candidate/replay
step, not meteorological calibration or a new live-policy deployment.

## Subsequent station-reference check

See P1_13_STATION_HANDOFF.md and P1_13_STATION_OBSERVATIONS.json for the later
one-time public station read requested by the user. Forty-four known station
values are now retained offline, separately from the forecast-only replay.
They are not at-point measurements, have not been interval-aligned, and were
not inserted into production. The point-report template is empty. Continuous
collection and accuracy evaluation remain unperformed. The six-file list above
records the initial candidate package; this follow-up adds three documentation
and evidence files.


## Subsequent P1-14 integration

P1_14_POLICY_DELIVERY_HANDOFF.md supersedes the earlier offline-only integration boundary for the current review worktree. The candidate can now be explicitly selected by both preview and live adapters and is tested inside the locked delivery path with isolated PostgreSQL and mocked LINE. The default remains v1, and production remains P1-12. This follow-up does not establish actual intraday provider acceptance, handset receipt or meteorological accuracy.


## P1-14 production follow-up

The authorized P1-14 code is committed and pushed, and the existing API now runs `intraday-v2-candidate` on successful deployment `08eda3b9-d345-40d3-8f75-cff4ff0b5eb3`. See `P1_14_POLICY_DELIVERY_HANDOFF.md` and `P1_14_PRODUCTION_RELEASE.json` for source, health, cadence and preservation verification. Earlier offline-only and P1-12/v1 statements describe the earlier stages. Positive real intraday LINE acceptance and handset receipt remain open; no qualifying event was fabricated to close them.
