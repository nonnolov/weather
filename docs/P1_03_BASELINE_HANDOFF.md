# P1-03 committed baseline dry-run handoff

Implemented 2026-10-10 Asia/Bangkok under user authorization to continue P1-03.
No production activation, commit, push, deployment, or LINE send.

## Added files

- app/notifications/intraday_baseline.py
- tests/test_intraday_baseline.py
- docs/P1_03_BASELINE_HANDOFF.md

The P1-02 comparator and all 19 pre-existing dirty files are protected and unchanged.
No runtime entrypoint, schema, dependencies, schedule, or daily behavior is changed.

## Read-only contract

evaluate_intraday_from_db(sessions, candidate, *, now,
known_location_reassigned=False) returns the existing immutable Decision.
The factory must be an engine-bound async_sessionmaker; a factory bound to a
caller's connection is rejected, preventing reuse of an uncommitted transaction.
The function owns its clean session and disables autoflush.

Candidate evidence is supplied as a frozen typed input. This step does not
ingest or select candidate source rows, invoke a provider, or imply that supplied
candidate evidence is itself durable. The caller must preserve source identity.

The current User assignment, Location timezone and active state are read from
database projections, avoiding stale ORM identity-map values. Browser identities,
missing/changed current locations, changed timezone, inactive locations, and
explicitly known location reassignment skip with reasons. Legacy evidence cannot
detect same-ID coordinate mutation; callers must flag known reassignment.

Latest history is scoped to exact channel/recipient/location and recognized key
prefixes rain:{location}: and rain-intraday:v1:{location}:, ordered by created_at
DESC then id DESC. No provider, evidence, freshness, or timezone filter can remove
a newest bad baseline and cause older-record fallback. These prefixes reflect
existing/proposed keys; this step creates no intraday deliveries or evidence format.
Unexpected rows within these reserved namespaces are treated conservatively.

The helper read_latest_rain_baseline requires a clean committed-history session.
It is exposed for testing/adaptation, not sufficient alone for send authorization.

Frozen evidence v1 provides original run ID, provider, retrieved/model timestamps,
timezone and ALL supplied hourly intervals, including unselected hours.
Naive timestamps mean UTC. Missing metrics remain None. Daily aggregates,
selection/rank and text do not drive comparison. Invalid schema/source/time/hour
content or inconsistent frozen local date skips. An extant conflicting source FK
skips; a null FK still uses the original ID frozen in JSON. Live ForecastRun or
HourlyForecast rows are never used to rebuild or repair baseline evidence.
Stored created_at remains an acceptance proxy, not proof of handset receipt.

All comparison thresholds, source/age gates, coverage, cooldown, reason ordering
and event identity remain delegated to the unchanged P1-02 comparator.
notify means dry-run comparison eligibility only.

## Verification and isolation

Synthetic file-backed SQLite databases are created independently per P1-03 case.
This permits separate-connection committed/uncommitted visibility checks.
Tests assert that evaluation executes SELECT statements only, retains delivery
JSON/count, never invokes LINE, ignores unrelated recipients/locations/channels/
namespaces, selects descending-ID timestamp ties, and never falls back from
unknown/unsupported/malformed newest evidence. They also cover rollback, current
assignment, source-FK loss/conflict, live-source mutation, naive UTC, identical
content, significant changes, cooldown, and DB error propagation.

The child process disables dotenv reads before app imports, overrides both DB
URLs with in-memory test defaults, clears LINE credentials, and blocks all
external socket connections. Loopback is allowed for Windows asyncio.
No production DB, live provider, notification CLI or LINE send is exercised.

Exact runner:

```powershell
Set-Location 'C:\Users\Nutchanon\source\repos\weather'
@'
import os,socket,ipaddress
os.environ.update({'DATABASE_URL':'sqlite+aiosqlite:///:memory:','DATABASE_URL_SYNC':'sqlite:///:memory:','APP_ENV':'test','DEBUG':'false','LINE_CHANNEL_ACCESS_TOKEN':'','LINE_CHANNEL_SECRET':''})
from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource._read_env_files=lambda self:{}
def guard(method):
 def checked(self,address):
  if self.family in(socket.AF_INET,socket.AF_INET6):
   try:allowed=ipaddress.ip_address(address[0]).is_loopback
   except ValueError:allowed=False
   if not allowed:raise OSError('External network disabled for P1-03 tests')
  return method(self,address)
 return checked
socket.socket.connect=guard(socket.socket.connect)
socket.socket.connect_ex=guard(socket.socket.connect_ex)
import pytest
raise SystemExit(pytest.main(['-q','tests/test_intraday_baseline.py','tests/test_intraday_comparison.py','tests/test_rain_alert_delivery.py','tests/test_rain_delivery_evidence.py']))
'@ | & C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -
Write-Output ('P103_TEST_EXIT='+$LASTEXITCODE)
```

## Limits and next work

This is a read-time preview, not an atomic pre-send authorization. No lock,
PostgreSQL concurrency claim, durable historical replay lookup, final locked
recheck, formatting, send, ingestion integration, ledger, scheduler, or activation
is added. DB errors propagate rather than become permission to notify. Current
assignment and baseline may change after reads; future send integration must
recheck under a shared recipient/location lock and use durable commit boundaries.
SQLite tests do not establish PostgreSQL concurrency or accepted-push/commit
failure recovery. Production/P0 scheduled acceptance remains outside this task.

Validation results will be appended after the final test run.

## Verified preservation checks

All 19 pre-existing dirty files matched SHA256 checkpoints: zero mismatches.
This includes all 16 protected earlier files plus all three P1-02 additions.
Tracked whitespace check returned 0. New-file no-index checks returned 1 for
differences against NUL, with only LF/CRLF conversion warnings and no whitespace
errors. Git index remained empty. Branch remained feature/frontend-ux and HEAD
fc3d29c5203916a26e3c6c0a33f3712cc263da2e.

Initial executed suite: 170 passed, 1 existing Starlette python_multipart warning,
86.94 seconds, exit 0. Final engine-bound-factory guard and its additional test
are included in the subsequent final run; that run's result follows below.

## Final executed result

Python 3.12.10 / pytest 8.2.0: 171 passed, 1 warning in 85.75s; process exit 0.
Breakdown: 42 new baseline integration cases, 117 unchanged comparator cases,
2 existing rain-delivery cases, and 10 existing frozen-evidence cases.
The sole warning is the existing Starlette python_multipart pending deprecation.

P1-03 read-only baseline integration and isolated regression validation passed.
This result is local SQLite validation, not production/PostgreSQL acceptance.
No commit, staging, push, deployment, live-provider request or LINE send occurred.
