# P1-12: scheduled intraday delivery implementation

Status: production deployment SUCCESS and live intraday enabled on 2026-10-10,
under explicit user authorization at 18:31:37 Bangkok. Local validation and rollout
evidence are separated below. The user subsequently requested commit/push to
the existing review branch; exact SHA and remote verification accompany that upload.

## Behavior

The existing API scheduler commits due forecasts, then chooses the original
preview adapter or the live adapter. INTRADAY_SEND_ENABLED is false by default.
Live requires the scheduler flag, a LINE token and an explicit nonempty
INTRADAY_SEND_RECIPIENT_IDS allowlist. Current active location assignment and
U-prefixed recipient discovery still apply; non-allowlisted recipients skip.
Configuration fails at startup if any required live setting is absent.

Live calls the existing locked deliver_intraday_update with dry_run=False and
durable_attempts=True. The same comparator, baseline, source verification,
daily/intraday recipient scope locks, formatter and frozen accepted evidence
remain authoritative. No significant eligible change means no LINE call.
Explicit API refresh hooks remain preview-only; the periodic worker is the sole
new live entrypoint. The 06:00 daily CLI/cron is unchanged.

## Durable failure protection

Migration 0007 adds intraday_send_attempts. This is send-intent bookkeeping,
not accepted history or a dispatch/retry queue. An independent transaction
commits pending intent with the event ID and exact frozen evidence before the
network call, while the original delivery transaction holds the rain-scope lock.
There are no foreign keys on intent: it must survive source/user deletion and
its independent commit must not wait on sender-held source/location locks.

A partial unique index allows at most one pending intent per recipient/location;
event identity is separately unique. Accepted status and delivery ID update in
the SAME transaction that commits NotificationDelivery. Cancellation, explicit
rejection, transport ambiguity, failure after acceptance and process crash
leave pending intent, so later live ticks/new processes cannot send another
notify event for that scope. The adapter never retries rejected/unknown sends.
Accepted evidence alone advances the weather baseline. Intent does not.

After committing intent, recheck freshness and event identity before pushing.
If the event expired or changed, leave pending and request operator review.
This favors omission over an automatic duplicate. It does not guarantee exactly
once handset delivery, or prove handset receipt from LINE API acceptance.

## Operator response

1. Disable INTRADAY_SEND_ENABLED and redeploy if sends need to be stopped.
2. Inspect pending intent/event and its frozen evidence in an owned read-only
   session. Inspect accepted delivery rows for the same recipient/location/event.
3. A pending row by itself is neither proof of LINE acceptance nor rejection.
   No accepted DB row is not proof that LINE rejected the request.
4. Do not delete intent, mark it accepted without matching durable accepted
   evidence, reset cooldown, regenerate old text from a new forecast or
   automatically retry. Unresolved scopes stay blocked across restarts.
5. Any evidence repair/rearming requires separately reviewed operator action.
   There is deliberately no automated reconciliation/reset endpoint in this task.

## Deployment preparation

Use the reviewed commit/archive when deployment is separately authorized.
Predeploy alembic upgrade head applies additive 0007; existing delivery rows
are untouched. Keep existing startup, replicas, daily cron and provider cadence.
Configure the live flag only with the explicitly authorized recipient allowlist
and messaging credential through existing secret handling, never repo/docs/logs.
No new service, dependency or paid upgrade is required.

Rollback means disabling live and redeploying, retaining the intent table.
Do not downgrade 0007: dropping the table removes unresolved-send protection.
The existing API previews can remain enabled without messaging credentials.
A synthetic weather alert must not be sent as a real weather warning just to
force acceptance. Controlled template testing, if requested, must be visibly
labelled and must not fabricate accepted weather baseline evidence.

## Verification record

Targeted initial run: 69 passed, one existing python_multipart warning,
81.14 seconds, exit 0. This preceded three additional concurrency/commit/new-source
regression cases and the final full-suite run; final results are recorded below.
An initial full run found 2 log-capture failures (437 passed): Alembic fileConfig
silenced unrelated existing loggers in the shared pytest process. The migration
test now restores pre-existing logger disabled states; the runtime logger is
unchanged and the original preview assertions remain intact.
Tests use dedicated PostgreSQL 16 at localhost 55434 and disposable schemas.
Live LINE/provider network is blocked; mocks inspect intent from a separate
connection before acceptance. The review worktree contains no dotenv file.
Production DB/provider/LINE was untouched by the local implementation/test step.

P1 remains open: real intraday production acceptance, longer-term cadence and
normal scheduled daily source-linked acceptance are separate evidence gates.

Final full run: 439 passed, 18 live integration cases deselected, one existing
python_multipart warning, 273.20 seconds, exit 0. No selected cases skipped.
This includes all 19 P1-12 cases: 18 live/config/guard cases and one real
PostgreSQL migration with seeded frozen history preservation. Original bridge
log assertions pass after migration-test logger isolation was fixed.

Preservation check: all 34 original dirty-file SHA-256 hashes match their
checkpoint; original feature/frontend-ux branch, fc3d29c HEAD and empty index
remain intact. Work is only in the isolated review worktree. No real LINE
call, production mutation, deployment, commit or push occurred during local implementation/testing.

## Authorized production rollout — 2026-10-10

The user explicitly approved deploying P1-12 and enabling real intraday LINE
for the existing recipient. Independent private read-only inspection confirmed
that the one active current LINE recipient matches accepted baseline delivery 5.
The allowlist is exactly that recipient; it is not an unrestricted active-user list.
LINE_CHANNEL_ACCESS_TOKEN references the existing weather-alert-cron variable;
CLI read-back verified the resolved credential matches without printing/persisting it.
Variables were set with skip-deploys, then one explicit CLI up applied the package.

Deployment bf7c1724-7445-4395-a40d-81056f8b80a9 reached terminal SUCCESS.
Package: git baseline 39e4471 plus exactly eight reviewed, tested runtime overlays;
74 allowlisted files, with exported INI fallback sanitized. This is not a P1-12
Git commit: deployment preceded the subsequently authorized review commit. Checkpoint with exact
file hashes is outside the build root in the local temporary directory.
All 68 deployed app/Alembic Python file hashes match the package (zero mismatches).

A fresh custom PostgreSQL backup was streamed through private PostgreSQL SSH:
C:/Users/Nutchanon/Backups/weather/weather-production-before-0007-20261010T113929Z.dump
145935 bytes, SHA256 7df17e3be642fe8ce68ea764e2ddc16208a71f978305241c7a65583b55935717.
PostgreSQL 18 pg_restore archive listing validated all eight table-data entries.
This new dump was not restored here; the earlier separate recovery rehearsal
remains historical evidence. No public database proxy or paid upgrade was used.
The initial CLI SSH backup attempt failed before migration; direct OpenSSH via
the CLI-generated temporary PostgreSQL config succeeded. Only the valid archive
above is the release backup; failed earlier artifacts are not recovery evidence.

Predeploy logs show 0006 -> 0007; private read-back confirms both unique indexes.
The original five accepted deliveries and frozen baseline remain present.
Settings read-back confirms live, scheduler and post-commit preview flags true;
one authorized active recipient and credential present. Internal/public health
checks return HTTP 200. Original start override, replicas, domain and daily cron
remain unchanged; cron deployment 6ffccaae-5764-47cf-89c9-c5e2d39b5287 was not restarted.

At 18:43:22.124 Bangkok, the deployed lifespan's first native LIVE cycle completed:
locations=1, refreshed=0, fresh=1, refresh_failed=0, processed=1,
statuses={suppress:1}, reasons={identical_content:1}, truncated=False.
It reused source 41 and correctly sent no message. Independent aggregate state:
five total deliveries, zero intraday deliveries, zero pending/accepted intents.
This proves live-path activation and suppression. A positive real intraday LINE
acceptance/handset receipt has not occurred; do not report it as proven.

The next tick is approximately 18:58:22 Bangkok plus processing delay. Since the
source was fetched around 17:48, that tick should be due for refresh if the service
continues running; its future result is not an observed fact. No synthetic weather
changes, manual cycle, forced alert or extra provider call was used for this rollout.
Later hourly refresh, positive significant-change delivery, long-term cadence and
normal scheduled daily acceptance remain observational gates for closing P1.

Rollback: keep this code and schema 0007, set INTRADAY_SEND_ENABLED=false and
redeploy; preview may remain enabled. Do not downgrade/drop the intent table.
Do not roll back directly to P1-11 with unchanged predeploy: that old package
does not know revision 0007. Preserve unresolved intents during any recovery.
See P1_12_PRODUCTION_LIVE.json for sanitized deployment/runtime evidence.
