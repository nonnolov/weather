# P1-04 PostgreSQL shared rain lock and post-lock recheck

Implemented 2026-10-10 Asia/Bangkok under explicit authorization for P1-04.
This stage implements and locally validates shared locking and locked dry-run
decisions. No intraday sender, CLI integration, scheduler, deployment or live
LINE action is added. Production/P0 acceptance remains separately gated.

## Changes

Added:
- app/notifications/rain_locking.py
- tests/test_rain_locking_postgres.py
- docs/P1_04_LOCKING_HANDOFF.md

Changed app/notifications/rain_alerts.py by exactly two lines:
one import and await lock_rain_scope(db, recipient_id, run.location_id) at the
start of send_rain_alert. Removing precisely those two additions reproduces its
pre-task SHA256. All other 21 pre-existing dirty files remain byte-identical,
including the P1-02 comparator and P1-03 adapter.

Daily recipient/location/date dedupe, thresholds, formatting, provider calls,
observation/evaluation behavior, source evidence and batch commit boundaries
remain as before. Daily now acquires the shared scope lock before reading its
location/formatting inputs, then retains its original daily-dedupe lock.
Daily keys and intraday keys remain distinct; both use the same scope lock.

## Shared-lock contract

rain_scope_lock_key hashes canonical namespace/channel/recipient/location with
SHA256 into a signed 64-bit integer. It is independent of date, source ID, event
ID and Python process hash seed. A hash collision causes additional serialization,
not permission for a duplicate send.

lock_rain_scope uses PostgreSQL pg_advisory_xact_lock and retains the lock until
the caller's transaction commits or rolls back. It leaves existing SQLite daily
tests unchanged; SQLite success makes no PostgreSQL concurrency claim.

locked_intraday_evaluation requires an engine-bound async_sessionmaker backed
by PostgreSQL READ COMMITTED. A factory bound to an existing connection cannot
reuse uncommitted caller state. REPEATABLE READ/SERIALIZABLE are rejected because
a pre-lock transaction snapshot may not see a delivery committed while waiting.
A transaction-local lock_timeout (default 3000 ms, bounded 1..60000 ms) prevents
an unbounded evaluator wait. Timeout and DB errors propagate, rollback and never
become permission to send.

After taking the advisory lock, the context locks the current User row FOR UPDATE
and Location row FOR SHARE, checks assignment/timezone/active status, then reads
the newest committed rain evidence through the unchanged P1-03 adapter. The
decision clock is sampled only after locks have been obtained, so waiting cannot
preserve obsolete source freshness, future-window or cooldown eligibility.
Known coordinate reassignment still requires the caller's explicit flag; legacy
evidence lacks coordinates and cannot establish same-ID coordinate stability.

The unchanged P1-02 comparator re-evaluates freshness, scopes, complete aligned
coverage, significance, cooldown and canonical event identity from frozen evidence.
A notify decision then checks the exact committed intraday event key in the same
channel/recipient/location. An existing event suppresses with
event_already_delivered and no actionable event ID.

The context yields LockedEvaluation(decision, session). Any FUTURE authorized
sender must perform acceptance and evidence persistence INSIDE this context.
Normal exit commits its transaction; exceptions/cancellation roll back.
This implementation itself adds no accepted-delivery record and invokes no sender.

evaluate_intraday_locked is a dry-run convenience that closes the context before
returning. Its returned decision MUST NOT authorize a later send: its locks are
already released. Two serial read-only previews can both report notify when no
accepted evidence is persisted between them. The test that shows one accepted
candidate advances baseline uses a synthetic delivery insertion under the first
worker's context, never a real LINE call.

## Executed PostgreSQL isolation and tests

A fresh temporary PostgreSQL 16 cluster was initialized using the already
installed binaries, with test role p104_test and loopback-only listener
127.0.0.1:55434. It is separate from the normal local PostgreSQL service and all
production databases. Each PG behavioral test creates a random
weather_p104_test_<UUID> schema, checks its search_path and drops only that
schema in cleanup. No application migrations or production schemas are changed.

The fixture rejects any target except the explicitly supplied dedicated test
URL/role/port. dotenv reads are disabled before application imports, both normal
app DB URLs are replaced with SQLite test defaults, LINE credentials are cleared,
and external socket connections are blocked. Loopback is permitted for asyncpg
and Windows asyncio.

The concurrency tests observe pg_stat_activity wait_event_type=Lock in the
test application's sessions; they do not infer contention from arbitrary sleeps.
They verify committed-state rechecks after advisory waits, row-lock protection
against user/location updates, clock sampling after waiting, cooldown, newest
unknown evidence without fallback, existing-event suppression, rollback,
timeout/retry, and two contenders with a synthetic accepted delivery.
The actual daily sender is also tested under the same scope lock with AsyncMock;
its mock push cannot occur until the lock holder releases.

Initial PG-specific run: 23 passed, 1 existing Starlette python_multipart warning
in 23.82 seconds, exit 0. Server reports PostgreSQL 16.15.

Final combined regression includes those 23 cases, 42 P1-03 cases, 117 P1-02
cases, 2 existing delivery cases, 10 existing evidence cases and 17 additional
daily-summary/rain-risk cases: 211 collected. Final result follows below.

Exact final runner:

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
   if not allowed:raise OSError('External network disabled for P1-04 tests')
  return method(self,address)
 return checked
socket.socket.connect=guard(socket.socket.connect)
socket.socket.connect_ex=guard(socket.socket.connect_ex)
import pytest
raise SystemExit(pytest.main(['-q','tests/test_rain_locking_postgres.py','tests/test_intraday_baseline.py','tests/test_intraday_comparison.py','tests/test_rain_alert_delivery.py','tests/test_rain_delivery_evidence.py','tests/test_daily_rain_summary.py','tests/test_rain_risk.py']))
'@ | & C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -
Write-Output ('P104_TEST_EXIT='+$LASTEXITCODE)
```

## Limits and next work

No intraday message formatting, real send, refreshed-candidate selection,
scheduler hook, provider polling, new services/dependencies/costs or activation.
Exact event-key replay is checked; a complete historical same-source mutation/
fingerprint replay audit across arbitrary older deliveries remains future work.
The current comparator already checks its supplied newest baseline's replay and
identical content; this stage does not invent a persisted evaluation ledger.

All competing accepted rain writers must respect the shared lock and persist
evidence before releasing it. Uncooperative direct DB writers are outside that
protocol. External LINE acceptance followed by commit failure can still cause a
duplicate retry; locks do not make network acceptance and DB commit atomic and
do not promise exactly-once or handset receipt. Daily still uses its existing
batch commit behavior. Transaction errors and cancellation release owned locks.

Next stage: reviewed intraday formatting and accepted-evidence/send integration
inside the context, including historical replay rules and mocked accepted-send/
commit-failure tests. Keep production activation gated separately.

## Final executed result and preservation

Python 3.12.10 / pytest 8.2.0: 211 passed, 1 warning in 129.25 seconds, exit 0.
All 23 PostgreSQL locking cases executed; none skipped. The other 188 cases
include isolated SQLite baseline integration and unchanged pure/daily regressions.
The sole warning is the existing Starlette python_multipart pending deprecation.

git diff --check returned 0. New-file no-index checks reported only LF/CRLF
conversion warnings, no whitespace errors. No staging occurred; branch remains
feature/frontend-ux, HEAD fc3d29c5203916a26e3c6c0a33f3712cc263da2e.
Of 22 pre-task dirty files, only the two-line shared-lock addition in rain_alerts.py
is changed; the other 21 are SHA256-identical. No commit, push or deployment.
The temporary cluster cleanup status follows after shutdown verification.

Verified cleanup: zero remaining P1-04 test schemas; the dedicated temporary
PostgreSQL instance stopped successfully and its generated cluster directory was
removed. The normal local PostgreSQL service was not stopped or modified.
Final protected-file check: zero unexpected SHA256 mismatches.
