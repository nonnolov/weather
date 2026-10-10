# P1-06 committed snapshot preview entrypoint

Implemented 2026-10-10 Asia/Bangkok after authorization to connect committed
snapshots to P1-05 and test an end-to-end preview. This is a manual preview
entrypoint, not production activation or a refresh job.

## Added files

- app/notifications/intraday_preview.py
- app/notifications/intraday_preview_cli.py
- tests/test_intraday_preview.py
- docs/P1_06_PREVIEW_HANDOFF.md

The 29 pre-existing dirty files were checkpointed by SHA256 before work.
No existing daily CLI, scheduler, ingestion path, comparator, formatter, schema,
dependency, or P1-05 delivery module is changed.

## Candidate construction and preview flow

read_committed_candidate(sessions, recipient_id, *, now) requires a private
engine-bound PostgreSQL async_sessionmaker. It opens a repeatable-read, read-only
transaction with a 3000 ms statement timeout. Assignment, location, latest
ForecastRun and hourly rows therefore come from one committed database view,
even if a writer commits a new version between queries. No caller-owned
uncommitted connection or ORM identity-map data is reused.

The recipient must begin with U and have an active current location with a valid
timezone. Runs are scoped to that exact location, ordered by retrieved_at DESC,
id DESC. The newest run is inspected without filtering unusable runs away.
Missing/unknown/unusable newest data never falls back to an older usable run.
No provider refresh is performed and no provider/model freshness is inferred.

valid_time is the hourly interval end. Every supplied row whose interval START
belongs to today's location-local date is frozen, including elapsed, unselected
and null-valued hours. The midnight-ending interval belongs to the prior start
date. Values are never replaced by zero. Metadata and the complete local-day
content produce an immutable Evidence candidate, independently of ORM rows.

After this read transaction ends, preview_committed_snapshots evaluates explicit
recipients in sorted, deduplicated order, with fresh clock samples per recipient.
It invokes P1-05 deliver_intraday_update with client=None and dry_run=True.
P1-04/P1-05 independently acquire READ COMMITTED scope/source locks, reread the
current assignment and durable baseline, verify the frozen candidate against
committed source rows, audit replay evidence, and rerun the final-clock comparison.
Only preview/skip/suppress is produced; no delivery insertion/baseline advancement.
SQLAlchemy database errors become error/database_error, without exception text
or retries. Cancellation and programming/configuration errors propagate.

## Manual CLI

After reviewed configuration, a manual preview can be run as:

```powershell
python -m app.notifications.intraday_preview_cli --recipient U_EXPLICIT_RECIPIENT
```

Repeat --recipient for an explicit batch. There is no --send option, implicit
all-user scan, sender client, provider ingestion, or scheduler integration.
--help and argument validation do not load database configuration. Ordinary
preview execution uses the configured app database; this task did not run that
command against the user's real database.

Default JSON output contains mode=preview, processed count, status counts and
reason counts, without recipient identifiers or message text. --show-messages
explicitly includes preview text, which contains a location name. DB errors
give exit code 1; successful previews/skips/suppressions give exit code 0.
The engine is disposed when the standalone command exits.

## Test isolation and coverage

Tests use a freshly initialized PostgreSQL 16.15 cluster from already-installed
binaries, listening only at 127.0.0.1:55434, with role p104_test/database postgres.
The role/port match the existing P1-04 fixture allowlist. Each PG test uses a
random weather_p104_test_<UUID> schema and removes it afterward. This is separate
from the normal local service and production database.

The Python runner disables dotenv reads before app imports, replaces ordinary
database settings with in-memory SQLite test defaults, clears LINE credentials,
and blocks non-loopback socket connections. No provider call or live LINE call
can occur. Earlier regression delivery cases inject AsyncMock only.

The 24 new cases cover help/argument validation and rejection of live-send
options; end-to-end read-only preview without delivery writes; uncommitted runs;
latest timestamp/id ties and no fallback; local-day midnight/unknown-hour
membership; missing/inactive/invalid assignment; missing/stale/incomplete source;
provider mismatch; assignment/source mutation between candidate construction and
locked evaluation; sorted deduplicated batch/fresh clocks; aggregate CLI output;
DB error sanitization and no retry; repeatable-read consistency during concurrent
commits; and rejection of factories without an owned engine.

An initial 22-case run had 20 passes and 2 assertion failures: the new tests
expected different missing-data reason names. Both expected values were corrected
to the existing comparator's incomplete_coverage; product logic was unchanged.
Two additional consistency/factory cases were then added.

Exact final isolated test runner:

```powershell
Set-Location 'C:\Users\Nutchanon\source\repos\weather'
@'
import os,socket,ipaddress
os.environ.update({'DATABASE_URL':'sqlite+aiosqlite:///:memory:','DATABASE_URL_SYNC':'sqlite:///:memory:','APP_ENV':'test','DEBUG':'false','LINE_CHANNEL_ACCESS_TOKEN':'','LINE_CHANNEL_SECRET':'','P104_TEST_POSTGRES_URL':'postgresql+asyncpg://p104_test@127.0.0.1:55434/postgres'})
from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource._read_env_files=lambda self:{}
def guard(method):
 def checked(self,address):
  if self.family in(socket.AF_INET,socket.AF_INET6):
   try:allowed=ipaddress.ip_address(address[0]).is_loopback
   except ValueError:allowed=False
   if not allowed:raise OSError('External network disabled for P1-06 tests')
  return method(self,address)
 return checked
socket.socket.connect=guard(socket.socket.connect)
socket.socket.connect_ex=guard(socket.socket.connect_ex)
import pytest
raise SystemExit(pytest.main(['-q','tests/test_intraday_preview.py','tests/test_intraday_delivery.py','tests/test_rain_locking_postgres.py','tests/test_intraday_baseline.py','tests/test_intraday_comparison.py','tests/test_rain_alert_delivery.py','tests/test_rain_delivery_evidence.py','tests/test_daily_rain_summary.py','tests/test_rain_risk.py']))
'@ | & C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -
Write-Output ('P106_TEST_EXIT='+$LASTEXITCODE)
```

## Activation boundaries

The newest source is selected at the candidate transaction's committed read point.
A subsequently inserted newer run is not automatically substituted; P1-05
verifies the chosen source and final-clock eligibility. This stage does not prove
production cadence, provider request budget, or snapshot immutability enforcement.
The existing source-row lock limitations and ambiguous accepted-send/commit
handling in P1-05 still apply to any future live integration.

Before production activation, review the existing authorized forecast refresh
path and actual cadence/budget, explicit rollout control, operational ambiguity
handling and scheduled P0 acceptance evidence. Do not attach rolling observation
ingestion or repurpose the daily CLI for intraday polling. No new cron/service,
production query, credential read, commit, push, deploy or actual LINE send was
performed in this task.

Final executed validation, preservation and temporary-server cleanup are recorded
below after completion.


## Final executed validation and cleanup

Python 3.12.10 / pytest 8.2.0: 268 passed, 1 warning in 157.47 seconds; pytest
exit 0. All 24 new preview cases and 244 earlier regression cases executed,
with none skipped. The warning is the existing Starlette python_multipart
PendingDeprecationWarning.

Tracked git diff --check returned 0. New-file no-index whitespace checks
returned 1 because the files differ from NUL, with only LF/CRLF conversion
warnings and no whitespace errors. All 29 protected pre-existing dirty files
again matched their initial SHA256 checkpoints: zero changes. Git index is
empty. Branch feature/frontend-ux and HEAD
fc3d29c5203916a26e3c6c0a33f3712cc263da2e remain unchanged.

Cleanup verified zero remaining disposable test schemas. The exact generated
P1-06 PostgreSQL cluster was stopped and its temporary directory removed.
The normal local PostgreSQL service was not stopped or modified.
No staging, commit, push, deploy, provider request or actual LINE send occurred.
