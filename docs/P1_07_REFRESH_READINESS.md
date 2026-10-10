# P1-07 existing refresh cadence and activation readiness audit

Executed 2026-10-10, approximately 16:07 Asia/Bangkok. User authorized the next
read-only audit after P1-06. Result: local P1 implementation is available, but
continuous intraday production activation is not ready. This task adds only
this review document; no runtime wiring or infrastructure changes.

## Scope and preservation

Repo: C:\Users\Nutchanon\source\repos\weather
Branch: feature/frontend-ux
HEAD: fc3d29c5203916a26e3c6c0a33f3712cc263da2e

All 33 pre-existing dirty files were checkpointed by SHA256 before this task.
No AGENTS.md was found under app/docs/tests. ripgrep was unavailable in the
remote PowerShell shell, so Get-ChildItem/Select-String were used for source
discovery. No local .env or credential file contents were displayed.

Railway plugin reads verified project weather:
71e0e499-6a9d-46c5-a552-b9a9da0e1928
production environment: 7ca11e27-30cd-4217-a80d-0b1647cb55c9.
Service configuration returned variable NAMES only; no values were requested.
No CLI install/update, new service, configuration mutation or live send occurred.

## Fresh platform evidence

| Service | Verified current configuration |
| --- | --- |
| weather-alert-cron, 7b46c113-c416-4571-ae05-7b697b4da7ec | python -m app.notifications.cli; cron 0 23 * * * UTC, daily 06:00 Bangkok; restart NEVER; one replica |
| weather-api, 89478e29-e136-4a39-9ace-3dc128d01495 | seed locations then uvicorn; predeploy alembic upgrade head; one replica; no cron configured |
| hermes-agent, 200a17bd-4063-4f1c-9f64-32b0d920b864 | separate hermes-railway root; no cron or weather DB variable name exposed in its service configuration; internal agent jobs were not inspected |

API latest deployment: 339511aa-cb47-4e95-a362-3bd664cba306, SUCCESS,
created 2026-10-10T03:07:40.740Z.
Cron latest deployment: 6ffccaae-5764-47cf-89c9-c5e2d39b5287, SUCCESS,
created 2026-10-10T03:09:48.991Z. Both have no staged changes.

Bounded cron runtime log read (2026-10-09T22:50Z to 2026-10-10T09:10Z):
- 2026-10-09T23:04:01Z: container started.
- 2026-10-09T23:04:10Z: observations: 4 locations, 96 created, 0 failed.
- Same log time: 1 sent, 4 skipped, 0 failed; 4 locations refreshed,
  0 refresh failed.

These logs show a daily job run around 06:04 Bangkok on October 10, BEFORE
the new P0 API/cron deployments at 10:07/10:09 Bangkok. They do not demonstrate
a scheduled delivery with the new frozen evidence code, or handset receipt.
The pending October 11 06:10 Bangkok P0 acceptance check remains relevant.

## Existing refresh and transaction map

| Path | Provider work and commit behavior | Intraday integration consequence |
| --- | --- | --- |
| notifications.cli | Rolling seven-completed-day user observations, then forecast refresh and daily LINE sender | Keep daily schedule/command; repeating this CLI repeats observations and sends daily messages |
| rain_alerts.refresh_and_send_rain_alerts | One forecast request per distinct current user location; includes browser locations; commits each refresh before daily sender | Existing daily forecast source, not an hourly-only job |
| POST users/{external_user_id}/forecast/refresh | Forecast-only request for user's current location; ingestion flushes, request dependency get_db commits after handler returns | Candidate evaluation must occur after successful commit using an owned session; a call inside the handler before dependency commit is too early |
| POST ingest/{location_id} | Forecast-only request for explicit location; same request commit dependency | Same post-commit boundary; no current periodic invocation proven |
| GET forecast and user forecast | Read stored snapshots only | Reading/polling these endpoints does not create fresh snapshots |
| ingestion.forecasts | Initial ingestion only for active locations with no existing run | Not periodic refresh; current live API start command overrides Docker's initial-ingestion command |
| frontend page | Explicit GPS/load flow calls refresh; no setInterval-based forecast refresh found in page.tsx | User-driven activity, not a guaranteed hourly source |

Source references inspected: app/ingestion/service.py, app/ingestion/forecasts.py,
app/notifications/rain_alerts.py, app/providers/open_meteo.py,
app/api/v1/users.py, app/api/v1/forecasts.py, app/api/v1/router.py,
app/core/database.py, app/main.py, Dockerfile and frontend/app/page.tsx.
Search of app Python code found forecast ingestion callers only in the two API
routes, initial ingestion and daily rain refresh. No application APScheduler,
schedule.every or asyncio.sleep forecast loop was found. This bounds the claim
to inspected code/platform configuration, not unseen external jobs.

Provider retrieval time is assigned after HTTP response; model_run_time remains
None. Hourly output resolution and a fresh retrieval timestamp do not establish
a newly initialized forecast model or changed weather content.

## Private production aggregate database evidence

Used the existing Git OpenSSH client and established weather-api-railway SSH
alias. A Python script was streamed over SSH stdin; no container file was
written. It used the deployed app session factory and a REPEATABLE READ,
READ ONLY transaction, with a local 5000 ms statement timeout. Queries returned
aggregate counts/times only. No recipient IDs, coordinates, message JSON,
database URLs, tokens or key material were printed.

Database audit clock: 2026-10-10T09:07:51.827469Z = 16:07:51 Bangkok.
- 5 users; 1 U-prefixed LINE candidate.
- 4 distinct active current user locations; 1 active current LINE location.
- Current LINE location has a snapshot; 0 latest snapshots within 90 minutes.
- Latest retrieval: 2026-10-10T05:21:11.927244Z = 12:21:11 Bangkok.
  Age at audit: approximately 226.7 minutes, exceeding the comparator's 90m gate.
- Current LINE location had 3 runs in the last 72 hours, all in the last 24h.
  Observed gap range: 8.824592 seconds to 24m45.563229s;
  median of the two observed gaps: 12.45323184 minutes.
  This tiny clustered sample does NOT establish recurring refresh cadence.
- Alembic schema revision: 0006.
- No latest accepted rain delivery exists for the current recipient/location
  rain namespaces; no compatible frozen baseline for that current scope.
- Separate aggregate historical check: 4 LINE rain delivery records, 0 with
  non-null rain_evidence, 0 matching the user's current location.
  Historical timestamps span 2026-10-06T23:02:52Z to 2026-10-09T23:04:08Z.

Do not copy evidence from the previous location, reconstruct/backfill old
delivery evidence from current forecasts, fabricate baseline, or send an extra
daily message just to unlock P1. A normal accepted daily delivery with committed
frozen evidence for the current location must establish a usable baseline.
Baseline compatibility/window coverage must still pass after that.

No P1 evaluator was executed against production in this task. From the observed
data, current-scope baseline is absent and current snapshot is stale. Those are
independent reasons why the data cannot support an eligible intraday update.

## Provider capacity and no-upgrade path

Official pages checked 2026-10-10:
- https://open-meteo.com/en/pricing
- https://open-meteo.com/en/terms
- https://open-meteo.com/en/docs/model-updates

Published free endpoint capacity is less than 10,000 calls/day, 5,000/hour and
600/minute, with a 300,000/month table limit. Free access is for non-commercial
use and has no uptime guarantee. This review does not determine the project's
commercial classification. No paid plan or upgrade is proposed.

One HTTP request is not necessarily one counted API call: the pricing FAQ
counts requests selecting over 10 weather variables or periods over two weeks
as multiple/fractional calls. Current forecast payload selects 18 hourly and
16 daily fields; archive payload selects 18 hourly fields. Exact accounting
weight for these payloads/shared egress usage was not measured. Do not label
the HTTP arithmetic below as a verified remaining API quota.

Let A = distinct active current user locations (observed 4), L = active current
LINE locations (observed 1), H = proposed refreshes/day, M = manual forecast
refreshes, I = initial ingestions, R = retries.
Raw weather-provider HTTP estimate: daily 2A + HL + M + I + R.
This assumes current daily forecast/archive attempts for all four locations,
with no failures/retries; future target changes alter the formula.

| Scenario | Additional forecast HTTP requests/day at L=1 | Interpretation |
| --- | --- | --- |
| Evaluate only after already-authorized refresh commits | 0 | Recommended first bridge; opportunistic, not continuous automatic coverage |
| Proposed hourly refresh across 24h | 24 | Unapproved scheduling/capacity example, not currently configured |
| 24h hourly example at L=100 | 2400 | Scales by distinct location, not recipient count; weighted quota and all existing usage still required |

Provider limits alone do not prove spare Railway runtime/memory/storage budget.
No billing values or account-wide egress usage were queried. Existing API has no
LINE Messaging token variable name; avoid adding live sender credentials merely
to enable a preview hook. No existing hourly weather scheduler was verified.
Creating a new service, multiplying daily cron frequency or attaching rolling
observations is not part of the recommended zero-additional-request bridge.

## Concrete next integration package (preparation, not implemented here)

Implement a disabled-by-default, preview-only post-commit bridge for an existing
explicit forecast refresh; reuse P1-06/P1-05. Do not add provider fetches.

Required sequence and behavior:
1. Existing authorized refresh finishes persisting all source rows.
2. Own request transaction commits successfully; rollback prevents any preview.
3. Only afterward, an owned session selects current eligible LINE recipients for
   that committed location. Never trust a caller-supplied user ID as live-send
   authorization; the current routes alone do not provide that guarantee.
4. Recheck current assignment/source/timezone/baseline under existing locks and
   explicit dry_run=True, client=None. Report counts/reasons only.
5. Preview failures do not undo the already committed successful refresh.
   No blind retry or durable delivery write. Cancellation remains cancellation.
6. Keep the flag off by default; do not attach it to observations, startup
   ingestion, generic GETs or the daily CLI. No scheduler/API response expansion
   or production configuration change as part of local preparation.

Tests for that package should prove real transaction ordering with isolated PG:
successful commit before preview; failed flush/commit/rollback produce zero
previews; unchanged/failed source refresh produces no fabricated candidate;
current recipient assignment changes are rechecked; shared location invokes one
candidate/read source without duplicate per-recipient execution; preview failure
leaves committed source intact; default-off behavior preserves existing paths;
no provider/LINE calls beyond the mocked original explicit refresh.

Before live activation, complete P0 scheduled frozen-baseline acceptance, verify
actual snapshot freshness/cadence and shared quota/cost headroom, review scope
authentication and explicit rollout control, and define operational handling of
ambiguous accepted-send/commit outcomes from P1-05. This audit does not authorize
a production bridge, hourly schedule, deployment or live push.

## Validation

This is a read-only audit and documentation-only addition. No new runtime code
was changed, so the prior 268-case P1-06 result remains the latest local runtime
test evidence; it was not rerun or misrepresented as a production test.
Final whitespace, protected-file hash and git state checks are recorded below.


Final checks: all 33 pre-existing dirty files match their pre-task SHA256 values,
zero mismatches. Tracked git diff --check returned 0. The new document's no-index
check returned 1 for differing content against NUL, with only a LF/CRLF warning
and no whitespace errors. Git index is empty; branch and HEAD remain as recorded.
Only docs/P1_07_REFRESH_READINESS.md was added. No commit, push, deployment,
database write, provider forecast/archive request, scheduler change or LINE send.
Official provider documentation reads and Railway read-only metadata/log reads
were performed; private SQL transactions returned aggregate data only.
