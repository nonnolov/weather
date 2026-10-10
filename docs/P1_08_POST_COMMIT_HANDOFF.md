# P1-08 default-off explicit-refresh post-commit preview

Implemented 2026-10-10 Asia/Bangkok. User instructed finishing P1 before GitHub
commit/push. Work continues in the isolated review worktree at
C:\Users\Nutchanon\source\repos\weather-p1-review-20261010,
branch review/p1-intraday-20261010, based on local commit 57eed05.
The original weather working tree is preserved. Nothing is pushed or deployed.

## Integration

New module: app/notifications/post_commit_preview.py.
New tests: tests/test_post_commit_preview.py.
Changes: app/core/config.py, app/core/database.py,
app/api/v1/users.py and app/api/v1/forecasts.py.

INTRADAY_PREVIEW_AFTER_REFRESH defaults to false. Only the two explicit forecast
refresh routes queue location/run identities after successful ingestion/counts.
No provider fetch is added. Existing daily CLI, observation ingestion, startup
ingestion, GET handlers and cron schedule do not queue previews.

get_db commits the source transaction before consuming the in-memory queue.
Handler, flush, commit failure or cancellation before commit clears the queue
and rolls back, with zero preview execution. BaseException handling includes
CancelledError. After successful commit, preview runs outside the rollback block:
its failure cannot undo the committed source.

Discovery validates exact committed location/run pairs, then reads sorted current
active U-prefixed recipients for those locations. A bound of 100 recipients per
request and 15-second total preview budget prevents unbounded request cleanup.
The in-memory queue deduplicates a location; it is consumed once. A truncated
batch is reported explicitly in the aggregate log. There is no durable queue,
background worker, retry or attempt to send later after releasing locks.

P1-06/P1-05 perform immutable candidate construction and their independent locked
assignment/source/baseline/final-clock rechecks. They run with client=None and
dry_run=True. Current latest source is selected at evaluation time, rather than
blindly using request ORM objects. No delivery evidence is inserted or advanced.
The preview discovery transaction closes before recipient evaluation sessions.

Default-off execution leaves explicit refresh behavior unchanged. After commit,
preview exceptions/timeouts produce a generic warning without IDs, coordinates,
exception strings or traceback; successful logs contain counts/status/reasons.
Cancellation after commit propagates but committed source remains intact.
Results are operational best effort, not added to the API response. A process
crash may lose a preview; losing an unsent preview is safe for this scope.

## Executed new tests

15 passed, 1 existing Starlette python_multipart warning in 18.00 seconds, exit 0.
Real PostgreSQL tests cover default off, commit-before-preview with actual newly
committed source/hour rows, no delivery write, handler/commit/cancel/flush failures,
post-commit exception/timeout/cancellation, deduplication and consume-once,
rejection of an open transaction, nonexistent or wrong-location run identities,
bounded/current/LINE-only discovery and both explicit API refresh routes.

A fresh PostgreSQL 16.15 cluster was created from installed binaries, separate
from the normal service: 127.0.0.1:55434, role p104_test, database postgres.
P1 tests use disposable weather_p104_test_<UUID> schemas; P0 migration evidence
tests use their own weather_p003_test_<UUID> schemas on that same test cluster.
No production credentials or database URL is used in local tests. dotenv reads
are disabled before imports. LINE credentials are cleared.

## Broader validation notes

The first all-repo run selected legacy integration tests as well as local tests.
Its default-config test expected APP_ENV=development, while the test runner had
overridden APP_ENV=test. This is a runner mismatch, not a product defect; source
tests were not changed to force a pass.

The legacy Bangkok integration test reported passed and can perform real public
Open-Meteo calls. The initial socket guard allowed loopback proxies, so it is not
proof that every outbound HTTP request was blocked. No LINE token was present;
no real LINE send or production DB mutation occurred.

The final run excludes the integration marker, removes HTTP/HTTPS/ALL proxy
environment variables before imports, retains non-loopback socket connect guards,
and uses APP_ENV=development with DEBUG=false and explicit isolated DB defaults.
This avoids selecting provider integration probes or treating proxy connections
as proof of network isolation. The complete final runner is recorded below.

```powershell
Set-Location 'C:\Users\Nutchanon\source\repos\weather-p1-review-20261010'
@'
import os,socket,ipaddress
os.environ.update({'DATABASE_URL':'sqlite+aiosqlite:///:memory:','DATABASE_URL_SYNC':'sqlite:///:memory:','APP_ENV':'development','DEBUG':'false','LINE_CHANNEL_ACCESS_TOKEN':'','LINE_CHANNEL_SECRET':'','INTRADAY_PREVIEW_AFTER_REFRESH':'false','P003_TEST_POSTGRES_URL':'postgresql+asyncpg://p104_test@127.0.0.1:55434/postgres','P104_TEST_POSTGRES_URL':'postgresql+asyncpg://p104_test@127.0.0.1:55434/postgres'})
for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
 os.environ.pop(key,None)
from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource._read_env_files=lambda self:{}
def guard(method):
 def checked(self,address):
  if self.family in(socket.AF_INET,socket.AF_INET6):
   try:allowed=ipaddress.ip_address(address[0]).is_loopback
   except ValueError:allowed=False
   if not allowed:raise OSError('External network disabled for P1 completion tests')
  return method(self,address)
 return checked
socket.socket.connect=guard(socket.socket.connect)
socket.socket.connect_ex=guard(socket.socket.connect_ex)
import pytest
raise SystemExit(pytest.main(['-q','-m','not integration']))
'@ | & C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -
Write-Output ('P108_TEST_EXIT='+$LASTEXITCODE)
```

## Activation and completeness boundary

This completes the reviewed source-refresh-to-preview bridge locally. It is not
an active automatic intraday sender. The P1-07 production facts still apply:
missing current-location frozen baseline, stale latest snapshot at that audit,
no verified hourly source cadence. Default remains off. Do not repurpose the
daily CLI or introduce recurring observation polling/new service.

Normal P0 scheduled acceptance on October 11, source cadence and resource budget,
scope authorization and ambiguous push/commit handling must be resolved before
live activation. A caller-supplied user ID in a public refresh path is not live-send
authorization. No send switch is exposed by this bridge. GitHub CLI will be used
for the GitHub workflow after P1's agreed completion boundary; no push in this step.

Final broad-suite result, original-tree preservation and temporary PG cleanup
are appended after execution finishes.


Initial all-repo result (before runner correction): 1 failed, 400 passed,
17 skipped, 1 warning in 199.92 seconds. The sole failure was
test_default_settings_load expecting development instead of runner override test.
The legacy real Bangkok API integration case reported passed; 17 Chon Buri
integration cases skipped because ordinary app DB settings were isolated SQLite.
This is recorded separately from the final 400 selected local cases and is not
used as live notification or production database acceptance evidence.

Preservation check during final run: original source working tree's 34 protected
dirty files all match their pre-Git SHA256 values. Original feature/frontend-ux,
HEAD fc3d29c5203916a26e3c6c0a33f3712cc263da2e and empty index are unchanged.
Review worktree remains at 57eed05 with exactly four runtime modifications and
four new P1-08/acceptance files; no new commit, push, merge or deployment.


## Final executed result

400 passed, 18 integration cases deliberately deselected, 1 existing Starlette
warning in 180.55 seconds; pytest exit 0. None of the 400 selected cases skipped.
Includes all 15 new P1-08 PG cases, all earlier P1 comparator/baseline/locking/
delivery/preview cases, four P0 PostgreSQL migration/evidence cases and broader
API/provider-mock/ingestion/observation/config/model/evaluation regressions.

Temporary PostgreSQL cleanup verified zero remaining P0/P1 disposable schemas;
the exact generated test server was stopped and its directory removed. Normal
local PostgreSQL was not stopped or modified. Tracked git diff --check returned 0.
No new commit, push, merge, deploy, scheduler change, or real LINE send occurred.
Original 34 dirty source files and original branch/HEAD/index remain unchanged.
The P1-08/acceptance package is four modified runtime files plus four new files
in the isolated worktree; the last local commit remains 57eed05.
