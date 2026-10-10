# P1-05 intraday formatting and mocked accepted-delivery integration

Implemented 2026-10-10 Asia/Bangkok under user authorization for the next local
stage: formatting, mock LINE acceptance and evidence persistence inside the P1-04
lock, including send/flush/commit failure behavior. No production activation.

## Added files and unchanged work

- app/notifications/intraday_formatter.py
- app/notifications/intraday_delivery.py
- tests/test_intraday_delivery.py
- docs/P1_05_DELIVERY_HANDOFF.md

All 25 pre-existing dirty files, including the daily P1-04 shared-lock change,
are protected by SHA256 checkpoints. No old formatter, comparator, baseline
adapter, locking module, runtime entrypoint, scheduler, schema or dependency
is changed by this step. No LINE credentials are read or used.

## Callable and default-safe behavior

deliver_intraday_update(sessions, candidate, *, clock, client=None, dry_run=True,
known_location_reassigned=False, lock_timeout_ms=3000) returns an immutable
IntradayDeliveryResult(status, decision, message, delivery_id).

Default preview requires no sender, makes no network call, writes no delivery
history and never advances baseline. Explicit dry_run=False requires an injected
async TextSender. Only AsyncMock is used in this task. No CLI, API, ingestion or
scheduler currently invokes this callable; adding it does not activate alerts.

P1-04 owns the READ COMMITTED PostgreSQL transaction and recipient/location
advisory lock, with current user/location row locks and clean session. P1-05
then validates candidate against an already committed same-location ForecastRun
and ALL its supplied hourly rows for the current location-local start date.
Input must provide that complete local-day snapshot coverage, including
unselected hours. The source ID must be the actual integer database run ID.
Provider, retrieval/model metadata and canonical hourly fingerprint must match.
A missing/uncommitted run, changed source metadata/values or incomplete supplied
source view skips candidate_source_mismatch before any push.

Share locks also protect the run and existing hourly rows during the network
await. Insertions of additional rows by an uncooperative writer are not prevented
by these row locks; snapshot immutability remains an application convention.

After source reads/locks, P1-05 freezes a new FINAL decision clock and reruns
the unchanged comparator, rereads/checks event identity and audits frozen
committed v1 intraday history under the still-held shared lock. This catches
freshness/horizon/cooldown expiry during source-lock waits. The initial P1-04
decision is preliminary; final evidence records the final decision clock.

Unknown/malformed history or incompatible comparison metadata skips
unknown_replay_history. Same source ID with changed canonical content on the
same local day skips inconsistent_historical_replay. Identical committed content
under the same recorded baseline/day suppresses historical_identical_content.
No history is altered, no suppressed-candidate ledger is invented and no older
baseline is used. Frozen JSON is still not tamper-proof at the database level.

## Message and frozen evidence

The separate formatter labels the text as an intraday forecast update, describes
the actual change reason and displays at most two periods containing triggering
intervals. Adjacent triggering intervals group; disjoint groups prioritize earlier
onset, then new rain/escalation, probability, hourly mm and chronological tie break.
The selected periods are displayed chronologically. Unchanged high-ranked periods
cannot displace all actual triggers. This does not change daily ranking.

Probability is the maximum within the displayed period; precipitation is maximum
HOURLY mm in that period. Neither is labeled a daily total. No incomplete source
sum is turned into a full-day claim. The message includes retrieval time, the
existing forecast URL and a short forecast-change caveat. Location names are
flattened to one line/bounded and the existing 5000-character client limit is
checked before pushing.

Evidence remains schema_version=1 with intraday template/selection versions,
mode, local date/timezone, original source/run metadata, ALL local-day hourly
intervals (including null/unselected values), selected periods and EXACT message
text. daily_aggregate is None. The comparison block records baseline delivery ID,
policy version, final evaluated clock, event ID, canonical candidate fingerprint,
reasons, complete decision window and every aligned baseline/candidate trigger.
No recipient/GPS is copied into JSON. Metrics that cannot round-trip into the
numeric JSON representation are rejected before send rather than silently rounded.

All text/evidence is created before the push await and kept independently of
mutable ORM/source objects. The only post-push DB operation is persistence of
that frozen record, never rebuilding from a newer run or querying latest weather.

## Acceptance, commit and failure behavior

After a normal injected push response, the acceptance clock supplies created_at.
The record uses rain-intraday:v1:{location_id}:{event_id}, links the source FK,
then flushes INSIDE the owned lock transaction. A sent result is returned only
after the context's commit completes; flush alone is not reported as durable.

- Explicit LineApiError propagates; no delivery record/baseline advancement.
- Timeout or httpx transport error raises SendOutcomeUnknown with the event ID.
  Acceptance may have happened; no automatic retry is performed.
- Cancellation during push retains CancelledError semantics, adds an ambiguity
  note, rolls back and releases locks. Do not blindly retry cancellation.
- A normal push followed by clock/flush/commit failure raises
  AcceptedDeliveryNotCommitted with event ID. Durable state is unconfirmed; a
  lost commit acknowledgement could hide an actual commit. Do not auto-retry.
- Exceptions/DB errors are never converted into notify/sent permission.

The sender has zero built-in retries. Locks cannot make external LINE acceptance
and DB commit atomic. Exactly-once and handset receipt are not promised.
Operational reconciliation for ambiguous acceptance/commit is still required
before production activation. An upstream job must not blindly retry these errors.

## Local tests and isolation

A NEW temporary PostgreSQL 16.15 cluster was created using already-installed
binaries, isolated from the user's normal local service and production. The
dedicated loopback-only URL/port/role matches the P1-04 fixture's allowlist:
127.0.0.1:55434, p104_test, postgres. The role name is reused only for fixture
compatibility; this is a freshly initialized P1-05 cluster.

Every PG case uses a random disposable weather_p104_test_<UUID> schema with
verified search_path, removed after its test. Source rows are synthetic and LINE
is always AsyncMock. The runner suppresses dotenv before imports, overwrites
normal DB URLs with SQLite test defaults, clears LINE credentials, and blocks all
external sockets while permitting local asyncpg/Windows asyncio.

Initial new suite: 27 passed, 1 existing Starlette warning, 24.00 seconds.
Expanded suite: 31 passed, 1 existing warning, 26.77 seconds.
Two additional final-clock/acceptance-clock cases are included in the final
combined run. Pure message/evidence tests and PG cases cover preview, committed
acceptance/replay, mock rejection/timeout/transport failure, post-push flush and
commit faults, source mismatch/uncommitted source, two actual callable contenders
with one mock push, protected source-row mutation, source FK deletion, historical
replay/unknown history, cancellation, earlier onset and precision preservation.

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
   if not allowed:raise OSError('External network disabled for P1-05 tests')
  return method(self,address)
 return checked
socket.socket.connect=guard(socket.socket.connect)
socket.socket.connect_ex=guard(socket.socket.connect_ex)
import pytest
raise SystemExit(pytest.main(['-q','tests/test_intraday_delivery.py','tests/test_rain_locking_postgres.py','tests/test_intraday_baseline.py','tests/test_intraday_comparison.py','tests/test_rain_alert_delivery.py','tests/test_rain_delivery_evidence.py','tests/test_daily_rain_summary.py','tests/test_rain_risk.py']))
'@ | & C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -
Write-Output ('P105_TEST_EXIT='+$LASTEXITCODE)
```

## Remaining activation work

This stage is a library callable, not an active intraday job. A next reviewed
integration must choose/construct committed candidate local-day evidence from an
authorized refresh path, provide production clock/client and explicit rollout
control, report preview/send/unknown outcomes, and establish ambiguity handling.
Verify available refresh cadence/request budget without adding services/costs.
No rolling observation ingestion should be attached to intraday evaluation.
Keep daily behavior and production/P0 acceptance gates intact. No schedule,
provider polling, new service, deployment, commit or push occurs in this task.

Final combined validation and cleanup result follows below.

## Final executed result

Python 3.12.10 / pytest 8.2.0: 244 passed, 1 warning in 129.95 seconds, exit 0.
All 33 P1-05 cases executed (10 pure formatting/evidence and 23 PostgreSQL/mock
delivery cases), along with 23 P1-04 locking-module cases (18 PostgreSQL and
5 engine/key guard cases) and the 188 earlier
baseline/comparator/daily regression cases. None skipped. The warning is the
existing Starlette python_multipart pending deprecation.

All 25 pre-existing dirty files matched their pre-task SHA256 checkpoints:
zero mismatches. Tracked whitespace check returned 0; new-file no-index checks
showed only LF/CRLF conversion warnings and no whitespace errors.
Git index remained empty; branch feature/frontend-ux and HEAD
fc3d29c5203916a26e3c6c0a33f3712cc263da2e are unchanged.
No commit, push, deployment, provider call or real LINE send.

Verified cleanup: zero remaining disposable test schemas; the dedicated P1-05
PostgreSQL instance stopped and its generated cluster directory was removed.
The normal local PostgreSQL service was not stopped or modified.
Final preservation check again found zero mismatches across all 25 protected files.
