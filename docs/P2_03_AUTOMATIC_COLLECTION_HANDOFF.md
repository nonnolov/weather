# P2-03: automatic durable station evidence

## Scope, dependencies and contract result

User authorized steps 1-3: review station time semantics, connect automatic collection separately from point data, test collection-to-report, then commit/push/deploy. The original weather worktree is protected; work is on review/p1-intraday-20261010, starting at fa80ebcfec47a472754f2005450058efa8e4dfbc. P2-01 and P2-02 local packages are included in this release.

The contract investigation is recorded in P2_03_TIME_CONTRACT_REVIEW.json. Official standard definitions and the public renderer provide useful evidence but do not authoritatively confirm the legacy endpoint's timezone/interval. This release automatically preserves that feed in quarantine. It does not claim that verification is complete or enable inferred-time scores. Independent reference acquisition remains an open minimum-P2 gate.

## Implementation

- Revision 0008 adds rain_station_fetches, independent of observations and notification tables. Each successful attempt stores provider JSON, exact decoded UTF-8 body, its SHA256 and collection time; failed attempts store only a sanitized error class. No station value becomes a current-point observation.
- An enabled API lifespan task starts after 90 seconds and polls once per hour from completion. A dedicated PostgreSQL try-lock excludes concurrent replicas. Unique station/UTC-poll-slot plus elapsed-hour due checks avoid duplicate requests. Cancellation rolls back and releases the lock.
- Streaming limits station responses to 2 MB, with a 15-second client timeout and 35-second cycle deadline. Redirects and environment HTTP proxies are disabled. Provider failures become durable history and wait for the next due tick; there is no immediate retry storm.
- P2_RAIN_COLLECTION_ENABLED defaults false. This rollout enables only the existing API service; no new service, volume or paid plan is introduced.
- GET /api/v1/rain-reference/status reads the latest attempt/success, source row counts, staleness and explicit scoring blockers. It performs no provider refresh and no LINE send. Its eligible_pairs=0/metrics=null reflect the open feed contract, not an accuracy score.
- Existing P1 lifespan is composed with the new task. Intraday policy, recipient allowlist and sending rules are unchanged. Cron and frontend deployments are outside this rollout.

## Verification and acceptance

Targeted tests: original audited pairing and point pipeline 104 passed; final collector-specific suite 18 passed, one existing python_multipart warning. New collector coverage includes actual isolated PostgreSQL locking, uniqueness, provider failures, cancellation/rollback, correction history, status reads, composed lifespan, streamed body cap and additive 0007 -> 0008 -> 0007 -> 0008 migration checks. Full regression and production verification are recorded after completion.

Minimum software acceptance: durable separated evidence, bounded one-hour polling, duplicate coordination, safe failures, a read-only report, local regression and verified deployed source. Minimum accuracy acceptance remains open until an aligned reference produces eligible real pairs; mock tests and quarantined known rows cannot close it.

## Release and rollback

Back up production before applying 0008. Export deployable backend files from the exact tested Git commit, sanitize only alembic.ini's local URL placeholder, and verify runtime hashes after Railway SUCCESS. Preserve previous notification evidence and pending intents.

Rollback collection by setting P2_RAIN_COLLECTION_ENABLED=false and redeploying this code, retaining station history. Schema 0008 is additive and old P1 code can operate with it; do not downgrade production or drop collected history as a routine rollback. P1 sending remains governed by its existing flags.

No manual observation is manufactured. This package does not improve ML, tune weather thresholds or infer instrument certification. Numeric station or point accuracy is not claimed.


## Completed local validation

Full isolated suite: 605 passed, 18 external integration cases deselected, one existing python_multipart warning; pytest 345.92 seconds, exit 0. Original worktree preservation check passed: 34 protected files unchanged, original branch/HEAD and empty index retained. P1 notification source is unchanged. Production backup before 0008 is a valid 161,452-byte PGDMP archive with nine table-data entries and a verified pg_restore listing, stored outside git. Deployment remains pending at this local-validation checkpoint.
