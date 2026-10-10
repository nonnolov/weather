# P1-10 automatic forecast-only preview integration

Implemented in the isolated review worktree on 2026-10-10. The user authorized
the ordered implementation, capacity review, testing and GitHub packaging.
Production deployment and live intraday LINE activation remain separate.

## Behavior and ownership

The existing FastAPI lifespan owns one cancellable background task when
INTRADAY_PREVIEW_SCHEDULER_ENABLED=true. Default false creates no task and makes
no DB/provider call. The existing explicit-refresh hook has its independent
INTRADAY_PREVIEW_AFTER_REFRESH flag, also default false.

The task waits 60 seconds after startup, then checks every 15 minutes after the
preceding cycle completes. It does not replay missed ticks. Each cycle uses a
PostgreSQL transaction-scoped nonblocking advisory lock for the complete batch;
another replica/process reports busy and performs no refresh/preview.

Only distinct active current locations with U-prefixed LINE users are eligible.
A row/assignment recheck occurs before fetching. A committed snapshot younger
than one hour is reused; due/missing snapshots use the existing forecast-only
ingestion service and are committed before preview in owned sessions.
Observations, daily CLI and real LINE client are never invoked.

Oldest locations are processed first, maximum 10 locations and 100 recipients.
A truncated batch is explicit and is not complete coverage. There is a
120-second cycle deadline, 15-second preview deadline, 3-second lock timeout,
and 5-second statement timeout. Forecast failure rolls back that source,
records a count and skips its preview. The next scheduled tick can attempt it
again; no immediate retry loop exists. Accepted-delivery evidence is untouched.

Preview uses the existing committed-candidate reader and final P1 locked
verification. Counts/status/reasons are logged without IDs, coordinates,
messages, traceback or credential-bearing exception text. Shutdown cancels the
owned task and releases the coordinator lock. Already committed sources survive
later cancellation or preview error. This task is best effort, not a durable
scheduler/queue or exactly-once polling guarantee.

## Capacity review without an upgrade

Fresh Railway metadata still shows one API replica and the unchanged daily
cron (0 23 * * * UTC; python -m app.notifications.cli). No service, schedule,
resource limit, environment value, paid dependency or plan changed.

A fresh API 1-hour metric read returned 61 samples: CPU mean 0.00216676,
peak 0.0377993; memory mean 0.116029 GB, peak 0.145570 GB. These are current
usage measurements, not a billing guarantee or proof of future headroom.

A fresh private read-only database aggregate audit found 11,474,623 database
bytes, 40 forecast runs, 6,720 hourly rows and 2,187,264 hourly-table bytes.
One active current LINE location has one committed frozen baseline. Raw counts
are saved in P1_10_CAPACITY.json; no recipient identities or coordinates are
included. Current storage is small; projected growth still requires monitoring.

At the observed one active LINE location, normal successful operation adds at
most approximately 24 seven-day forecast HTTP requests/day, before manual/daily
refresh overlap and restart timing. Successful polling reuses sources younger
than one hour. Persistent provider failures can yield up to approximately 96
attempts/day per location (15-minute ticks), since unsuccessful retrievals do
not create a fresh committed snapshot. Cycle time/downtime reduce those numbers.
The maximum 10-location batch bounds work, not account-wide monthly usage.

Each successful seven-day snapshot stores roughly 168 hourly and 7 daily rows.
At 24 successes/day and one location that is about 4,032 hourly + 168 daily
rows/day (120,960 hourly rows over 30 days), plus existing daily/manual work.
No retention deletion was added; history is preserved. This growth must be
observed after rollout. It is not valid to promise zero additional billed usage.

Official provider sources checked today:
- https://open-meteo.com/en/pricing
- https://open-meteo.com/en/terms

The published free non-commercial endpoint has 10,000/day, 5,000/hour,
600/minute and 300,000/month limits. Requests selecting more than 10 variables
can count as multiple calls. Current forecasts request 18 hourly and 16 daily
variables, so raw HTTP estimates are not measured weighted quota usage.
No paid endpoint/API key was added and no plan upgrade is required by this
implementation. Account-wide/shared-egress usage and commercial classification
were not determined. Existing API use incurs its normal Railway resource costs.

## Validation

Targeted real PostgreSQL + mocked network checks: 35 passed, one existing
Starlette warning, 45.61 seconds, exit 0; includes 20 new scheduler cases and
15 existing post-commit cases. Tests cover age boundaries, source commit before
real preview, fresh-source reuse, shared-location dedupe, inactive/browser
exclusion, concurrent cycles, cancellation/lock release, source/commit failures,
post-commit preview failures/deadlines, current assignment rechecks, oldest
bounded batches, recipient bounds, disabled behavior, actual API lifespan task
ownership and serial no-catch-up looping.

Full regression: 420 passed, 18 live integration tests deselected, one existing
warning, 231.11 seconds, exit 0. No selected cases skipped. The dedicated test
cluster was stopped and removed, and all 34 original protected files matched
their checkpoint hashes. Original branch, HEAD and empty index are preserved.
The current acceptance boundary is recorded in P1_ACCEPTANCE.md.
Tests use the disposable localhost PostgreSQL 16 instance at port 55434 and
random schemas, with dotenv reads disabled, LINE credentials cleared, external
socket connections blocked, proxy variables removed, and integration probes
excluded. No production provider refresh or LINE send is part of these tests.

The Windows pg_ctl launcher returned a pipe-capture timeout after the server
had started. Independent pg_ctl status verified the dedicated data directory,
PID and port; all PostgreSQL tests executed against that running instance.
Stopping the verified instance released the launcher's captured pipe, and its
wrapper exited 1. This launcher outcome is separate from the targeted and full
pytest exit-0 results. The verified instance stopped with exit 0 and its exact
temporary directory was removed; no normal PostgreSQL service was touched.

## Rollout and rollback

After reviewing the package, deploy the review commit to the API with its
existing start/predeploy commands, then set the two preview flags true.
Verify deployment SUCCESS and aggregate scheduler logs (including busy,
truncation/errors), source timestamps and baseline evidence across actual ticks.
No token needs to be added to API for preview. Do not multiply the daily cron
frequency. Setting both flags false disables further task work on the next
deployment; an already executing cycle ends/cancels with that deployment.
No schema change is required. Baseline/delivery history remains intact.

Production automatic cadence, billing impact and deployed-lifespan behavior
cannot be established by local tests or an in-memory one-off process. The
October 10 controlled accepted daily baseline resolves immediate baseline
readiness, but does not prove the normal scheduled daily job after its release.
A real intraday sender is still not wired or activated. This package completes
automatic preview preparation, not continuous production LINE activation.
