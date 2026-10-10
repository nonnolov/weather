# P1-11 production preview rollout — 2026-10-10

The user explicitly authorized deploying and enabling production preview.
Only weather-api in the existing production environment was deployed.
No live intraday LINE sender, new service, paid dependency or plan upgrade was
introduced. The daily LINE cron remains on its existing deployment and schedule.

## Deployment identity

- Source commit: 6eda58f9f3bf497b407ce4ebbdc213ab30ec2804.
- API service: 89478e29-e136-4a39-9ace-3dc128d01495.
- Project: 71e0e499-6a9d-46c5-a552-b9a9da0e1928.
- Production environment: 7ca11e27-30cd-4217-a80d-0b1647cb55c9.
- New deployment: 515a5c49-b042-4833-bd30-23ba3fef97ba, observed SUCCESS.
- Prior API deployment: 339511aa-cb47-4e95-a362-3bd664cba306.
- Existing daily cron deployment: 6ffccaae-5764-47cf-89c9-c5e2d39b5287.

A clean git archive of the exact source commit was exported to a temporary
local directory and uploaded with Railway CLI to the explicit existing API
service/environment. No source connection or autodeploy trigger was added.
The original working tree and review code were not rewritten for deployment.
Both preview variables were set with skipDeploys=true, then the single code
deployment applied them: INTRADAY_PREVIEW_AFTER_REFRESH=true and
INTRADAY_PREVIEW_SCHEDULER_ENABLED=true.

The existing API start command (seed locations then uvicorn), predeploy
alembic upgrade head, service domain, replica/resource settings and daily cron
command/schedule remain unchanged. Startup logs reported schema context and
zero created/four existing seed locations skipped. App startup completed at
2026-10-10T10:47:20Z (17:47:20 Bangkok).

## Runtime validation

Private SSH readback verified all 57 app Python source hashes match the archive,
with zero mismatches. The running settings have both preview flags true and no
LINE_CHANNEL_ACCESS_TOKEN. Internal /health returned HTTP 200.

One authorized forecast-only ingest POST through the actual deployed API
returned HTTP 201 and source 41. This exercised the real request commit and
post-commit hook, rather than calling a comparator in an isolated process.
The aggregate hook log reported processed=1, suppress=1,
identical_content=1, truncated=False.

The audit read committed aggregate state before/after in private read-only
transactions: five total delivery records and zero intraday delivery records
were unchanged. Source 40 was replaced as the latest snapshot by fresh source
41; the original immutable source and accepted delivery baseline remain in
history. No message text, recipient identity, coordinates or credentials are
included in P1_11_PRODUCTION_PREVIEW.json.

Native scheduled-tick evidence is appended below after its startup delay.
The scheduler checks every 15 minutes after each completed cycle, refreshes
only due active current LINE locations (snapshot age >= one hour), and runs
preview using committed data. It does not execute observation ingestion or
LINE delivery. Repeated long-term cadence, weighted provider quotas and future
billing impact still require observation; a startup tick alone does not prove
continuous uptime or all later refreshes.

## Rollback and remaining scope

Set both API preview flags false and redeploy to stop the owned task and
request hook. If the new API code itself fails, the prior API deployment above
is the rollback target; do not touch Postgres or delete evidence/history.
The periodic worker has bounded scope/deadlines and a PostgreSQL cycle lock.
Failures log aggregate status and preserve already committed snapshots.

The normal post-release daily cron's accepted frozen evidence remains a
separate scheduled-path verification. It was neither redeployed nor manually
started here. Real intraday LINE activation remains a separate authorized
rollout and is not wired into API or scheduler. Local regression remains
420 passed, 18 integration probes deselected, one existing warning.

## Native scheduled tick observed

At 2026-10-10 10:48:20 UTC (17:48:20 Bangkok), the deployed lifespan's first
native scheduled cycle completed after its 60-second startup delay:
status=complete, locations=1, refreshed=0, fresh=1, refresh_failed=0,
processed=1, statuses={suppress:1}, reasons={identical_content:1},
truncated=False. It correctly reused source 41, refreshed moments earlier by
the authorized API check. This is an automatically timed container task, not a
manually invoked cycle. The next tick is approximately 18:03:20 Bangkok plus
any processing delay; later hourly due-source refresh is not yet observed.

The deployed API has no messaging token and the preview paths have no live
send option. Both request-side and scheduled preview logs are included in the
sanitized runtime report. The first timed cycle verifies task activation and
fresh-source reuse; it does not replace longer-running freshness/capacity
observation. Original protected worktree hashes are checked after packaging.
