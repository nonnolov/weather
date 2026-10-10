# P1-02 pure comparator handoff

The user approved the P1 comparison policy on 2026-10-10 Asia/Bangkok. That
approval supersedes the proposal status in P1-01 for this isolated implementation
only. There is no production activation or P0 scheduled acceptance evidence.

Added only `app/notifications/intraday_comparison.py`,
`tests/test_intraday_comparison.py`, and this document. Existing runtime, tests,
configuration, schema, and design documents remain untouched.

## Contract

`compare_intraday(baseline, candidate, *, now) -> Decision` takes frozen typed
`Scope`, `Hour`, `Evidence`, and `Baseline` records. The caller supplies the newest
durable accepted rain delivery and adapts frozen evidence v1, including unselected
hourly rows. Null or unsupported newest evidence skips; there is no older-record
fallback. The comparator imports no ORM, session, settings, provider, or sender.

`Decision.outcome` is `skip`, `suppress`, or `notify`; notify means comparison
eligibility only. Reasons are explicit, triggers contain immutable aligned UTC
baseline/candidate values, and notify includes a stable event digest. Multiple
triggers form one decision, ordered earlier onset, new rain, escalation. New rain
also meets escalation by definition. Cooldown suppressions retain triggers but
have no event ID and never advance a baseline.

Approved constants are 70% OR 10 hourly mm strong; +20 percentage points OR
+5 hourly mm; six-hour horizon, at least two complete hours; candidate age <=90m,
baseline source and delivery age <=24h; cooldown >=3h; onset advance >=2h with
candidate lead <=4h. Boundaries are inclusive. The six-hour window makes an onset
advance >=2h with lead beyond 4h impossible on the hourly grid.

The contract uses exact absolute `(start,end]` intervals, naive times as UTC, and
interval-start membership in today's location-local date. The candidate's first
future boundary supplies only the hourly phase, supporting UTC offsets such as
`:30`. W fills every slot of that phase independently of available overlap or row
count; missing leading or trailing hours cannot shorten it. Null metrics outside W are allowed
as unknown; malformed supplied intervals/metrics and duplicate keys skip. No
unknown metric becomes zero. Complete candidate and baseline coverage of W is
mandatory. Invalid inputs return deterministic skip decisions.

`canonical_fingerprint(evidence) -> str | None` hashes all supplied normalized
hourly coverage, provider (trimmed/case-normalized), and timezone (trimmed, valid
IANA key). It normalizes numeric forms and order, excludes source IDs/times/model
metadata, and has no daily/rank/text/arbitrary JSON input. Timezone aliases are
not silently equated. Same-ID changed content skips as inconsistent replay;
identical newer content suppresses despite changed IDs. Exact same-ID replay can
suppress at equal retrieval; other equal/older retrieval skips. Event identity
contains baseline delivery ID, policy version, and canonical triggering intervals,
reasons, and aligned values; candidate IDs and retrieval times do not alter it.

## Local validation

The required absolute interpreter invocation below failed before pytest with
PowerShell `CommandNotFoundException`: the executable was unavailable inside the
sandbox. A preceding `Test-Path` also reported `Access is denied`. The coding-agent sandbox did not execute pytest. The parent reviewer subsequently
executed the final suite successfully; see the verified result below.

Exact attempted command, runnable by the parent from the repository root:

```powershell
@'
import os
import socket
os.environ.update(DATABASE_URL='sqlite+aiosqlite:///:memory:', DATABASE_URL_SYNC='sqlite:///:memory:', APP_ENV='test', DEBUG='false', LINE_CHANNEL_ACCESS_TOKEN='', LINE_CHANNEL_SECRET='')
from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource._read_env_files = lambda self: {}
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
def local_only(method):
    def guarded(self, address):
        if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1', 'localhost'):
            raise RuntimeError('External network disabled for pure comparator tests')
        return method(self, address)
    return guarded
socket.socket.connect = local_only(_original_connect)
socket.socket.connect_ex = local_only(_original_connect_ex)
import pytest
raise SystemExit(pytest.main(['-q', '--noconftest', 'tests/test_intraday_comparison.py']))
'@ | & 'C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe' -
```

`--noconftest` excludes existing shared app/DB fixtures; these tests use no DB or
asyncio fixtures. Child environment and dotenv suppression precede app imports.
External socket connections are blocked; loopback remains allowed for Windows
asyncio. No `.env`, live CLI, external provider, LINE, or production DB is used.

Actual static commands:

```powershell
git diff --check
git diff --no-index --check -- NUL app/notifications/intraday_comparison.py
git diff --no-index --check -- NUL tests/test_intraday_comparison.py
git diff --no-index --check -- NUL docs/P1_02_COMPARATOR_HANDOFF.md
```

`git diff --check` returned 0. Each new-file check returned 1 for differences
against NUL, with no whitespace errors; output contained only LF-to-CRLF warnings.
SHA256 checks confirmed all 16 pre-existing dirty files match their initial bytes,
including every P0 runtime/test file. Branch remains `feature/frontend-ux`; HEAD
remains `fc3d29c5203916a26e3c6c0a33f3712cc263da2e`. No git staging, commit, push,
or checkout occurred. Only the three authorized new files appear additionally.

## Remaining limits and next step

No baseline query, committed replay-history lookup, lock, display-period choice,
ingestion, send, commit, ledger, scheduler, or deployment is implemented. Callers
must preserve location identity and reject known reassignment; legacy evidence
cannot detect same-ID coordinate mutation. The function compares only the supplied
baseline, so it cannot verify durability or source mutation against other history.
Local pure tests cannot validate PostgreSQL concurrency, accepted-send/commit
failure recovery, provider cadence, or P0 scheduled acceptance.

Next step: baseline DB integration requires separate review and approval. Runtime
integration, P0 scheduled evidence, and production activation remain pending.

## Parent reviewer verified result (2026-10-10)

The first parent run reported 118 passed and 1 failed: the older-source test
fixture also exceeded the 90-minute freshness limit, correctly producing
`stale_candidate` before source-order validation. The final fixture isolates
source order using fresh candidates. Production policy was not weakened.

After the coding agent completed, the parent executed Python 3.12.10 with
pytest 8.2.0 against the final files:

- `tests/test_intraday_comparison.py`: 117 passed.
- `tests/test_rain_alert_delivery.py`: 2 passed.
- `tests/test_rain_delivery_evidence.py`: 10 passed.

Actual combined result: **129 passed, 1 warning in 0.74s**, process exit 0.
The warning is the existing Starlette `python_multipart` pending deprecation.
Unlike the isolated attempted command above, this successful combined run used
the repository conftest. Before imports, the parent disabled dotenv reading,
set both DB URLs to in-memory SQLite, selected test environment, and cleared
LINE credentials in the child process. Socket connect/connect_ex allowed only
loopback IPs for Windows asyncio; all external network connections were blocked.
The actual pytest arguments were `-q tests/test_intraday_comparison.py
tests/test_rain_alert_delivery.py tests/test_rain_delivery_evidence.py`.
No live provider, production DB, notification CLI, or LINE send was exercised.

Final reviewer SHA256 comparison: zero mismatches across all 16 protected
pre-existing dirty files. `git diff --check` passed; index empty; branch and HEAD
unchanged. Only the three authorized task files were added. Acceptance criteria
for the isolated pure comparator and local regression checks passed. Actual
scheduled operation, durable baseline lookup, concurrency, and end-to-end LINE
delivery remain unverified and outside this task. No commit, push, or deploy.
