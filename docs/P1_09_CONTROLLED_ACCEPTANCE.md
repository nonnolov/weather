# P1-09 controlled production acceptance — 2026-10-10

The user authorized a controlled forecast refresh, one real daily LINE push to the registered active current-location recipient, durable frozen evidence, and P1 preview only. The recipient guard required exactly one eligible LINE user. No intraday LINE push was authorized or performed.

## Results

| Check | Result |
| --- | --- |
| Schema | 0006 |
| Preflight | One eligible recipient; today's current-location daily key absent; preview skipped no_baseline |
| Forecast refresh | One committed run, source ID 40 |
| Daily LINE push | One API acceptance, message length 340 characters |
| Durable delivery | One committed record, delivery ID 5 |
| Frozen evidence | Schema v1, matching source ID, exact message retained, 24 hourly intervals |
| P1 preview | suppress / identical_content |
| Independent read-only recheck | Today's daily key exists; suppress / identical_content |

Machine-readable sanitized results and reviewed source hashes are in
P1_09_CONTROLLED_ACCEPTANCE.json. P1_09_PREFLIGHT.json contains the final read-only
recheck. Recipient identity, coordinates, credentials and message text are not
included in these reports.

## Execution boundary

A private SSH one-off process imported the reviewed notification modules in memory,
including the evidence ORM and shared scope locks. It used the existing API database
session factory and ingestion service. No deployed files, environment variables,
service configuration, cron schedule or deployment changed. The messaging credential
was read from the existing cron service and used only in memory; it was not written
to disk, arguments, reports or API service configuration.

The one-off process committed the forecast before sending. It locked the current
assignment and location again before sending, froze formatter inputs, awaited one
LINE push, and committed its delivery evidence. There was no automatic retry.
LINE API acceptance is an acceptance proxy; handset receipt is not independently
verified. The preview has no LINE client and writes no delivery baseline.

A local Windows encoding error stopped the first read-only probe before SSH input
was transmitted. The corrected read-only probe succeeded; this did not cause any
production write or duplicate send.

## Remaining production scope

This proves the fresh snapshot -> accepted daily frozen baseline -> committed-history
P1 comparison path today. It does not prove recurring fresh snapshot cadence,
automatic P1 production wiring, the post-commit hook in the deployed API, or the
next normal cron execution. P1 preview remains default-off and undeployed. A real
intraday trigger and intraday send were not forced using fabricated weather.

Local regression evidence remains 400 passed, 18 live integration tests deselected,
one existing warning. No additional commit, GitHub push, merge or deployment was
performed for this controlled check. Original repository files are preserved.
