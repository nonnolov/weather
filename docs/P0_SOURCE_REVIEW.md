# P0-02/P0-03 source review and proposed commit

Reviewed 2026-10-10 Asia/Bangkok. Preparation only; no staging, commit, push, checkout, deployment, production commands, ingestion, LINE sending, database access, or test execution.

Branch: `feature/frontend-ux`.
HEAD: `fc3d29c5203916a26e3c6c0a33f3712cc263da2e`.

Review scope: current P0 tracked diff and five untracked P0 files only. Read [P0_RELEASE_PLAN.md](P0_RELEASE_PLAN.md), relevant [PROJECT_STATE.md](PROJECT_STATE.md), and [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md). Scheduler/ingestion entrypoints were read only to identify intraday dependencies. This is not a repository-wide audit. Older project-context branch, seed-alert, migration, and release statements are historical; current Git observations and the release plan take precedence.

## Exact file inventory

The initial working tree contains 12 existing dirty files: seven tracked modifications and five untracked files. Preserve all 12 byte-for-byte.

| Initial status | Path | Reviewed scope |
| --- | --- | --- |
| Modified | `app/models/notification.py` | Nullable source link and JSON evidence |
| Modified | `app/notifications/formatter.py` | Rain interval local-day membership |
| Modified | `app/notifications/rain_alerts.py` | Interval selection and frozen delivery evidence |
| Modified | `app/notifications/rain_risk.py` | Preceding-hour boundaries and local date |
| Modified | `docs/RAILWAY_HANDOFF.md` | P0 review, previous tests, release evidence |
| Modified | `tests/test_daily_rain_summary.py` | Interval fixtures and formatter regression |
| Modified | `tests/test_rain_risk.py` | Interval, timezone, midnight regressions |
| Untracked | `alembic/versions/0006_rain_delivery_evidence.py` | Additive migration after 0005 |
| Untracked | `docs/P0_RELEASE_PLAN.md` | Export, release, rollback, verification record |
| Untracked | `tests/test_rain_delivery_evidence.py` | Frozen evidence and delivery regressions |
| Untracked | `tests/test_rain_evidence_migration.py` | Isolated SQLite migration regression |
| Untracked | `tests/test_rain_evidence_postgres.py` | Opt-in isolated local PostgreSQL regression |

This task adds only `docs/P0_SOURCE_REVIEW.md` and `docs/P1_01_INTRADAY_BRIEF.md`. Proposed commit inventory is these 14 explicit paths. No runtime or test file is changed by this task. Final SHA256 comparison confirms all 12 original files retain their initial bytes; branch and HEAD remain unchanged.

## Findings

No new material mismatch or blocking defect was identified in the scoped diff. This conclusion is static review, not new execution evidence.

- P0-02 consistently treats hourly rain timestamp `t` as interval `(t-1h, t]` across selection, formatter, and evidence. Naive timestamps represent UTC. Local-day membership follows interval start; an interval ending at Bangkok midnight belongs to the preceding day. Stored `valid_time`, snapshots, and provider daily `forecast_date` remain unchanged.
- Rain thresholds, scoring, top-two selection, daily freshness, recipient/location/day dedupe, and the daily schedule remain intact. Strong selection uses probability >=70% OR hourly rain >=10 mm; fallback uses >=30% OR >=5 mm. Daily aggregates remain separate from period values.
- P0-03 freezes the supplied run and formatter result before network await. It stores UTC source timestamps, nullable model time, versions, mode, selected periods in score order, hourly intervals, daily aggregate, and exact message text. Evidence is attached only after LINE API acceptance. No latest-run re-query substitutes provenance.
- Migration 0006 is self-contained and additive: nullable integer FK, nullable JSON, no default or backfill, `ON DELETE SET NULL`. ORM and migration agree. Legacy/non-rain evidence remains unknown. Run deletion preserves JSON, including original source ID. Existing unique dedupe remains unchanged.
- Reviewed tests cover three modes, source/latest mutation, supplied-run identity, skip/failure/retry paths, selected-period order, midnight, naive UTC, daily-versus-period values, and migration preservation. PostgreSQL tests require explicit loopback URLs without query overrides, create an isolated schema, and clean up that schema. They were read, not executed here.
- Known limitations remain: LINE push precedes durable DB commit; a commit failure can lose evidence and allow duplicate retries. LINE acceptance is not handset receipt. Location deletion still cascades delivery history. Evidence has no DB-enforced write-once policy and is not tamper-proof. Exact stored text preserves the displayed location name; structured evidence does not separately freeze that display name, so general reformatting must not reconstruct it from a changed live location. These are limitations, not newly introduced blockers.
- Current daily helpers do not implement intraday comparison or cooldown. Their daily dedupe intentionally suppresses a second send for the same recipient/location/day. Do not weaken it during P0 source preparation.

## Cron overlay comparison performed here

Compared corresponding files under:
`C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\alert-cron`.

Raw byte lengths and SHA256 were compared. A separate UTF-8 comparison explicitly allows only CRLF-to-LF normalization. Normalized equality alone would not establish byte equality; here every file passes both comparisons.

| Path | Working/export bytes | Raw byte equality | CRLF-normalized equality |
| --- | --- | --- | --- |
| `app/models/notification.py` | 1703 / 1703 | Equal | Equal |
| `app/notifications/formatter.py` | 5369 / 5369 | Equal | Equal |
| `app/notifications/rain_alerts.py` | 9683 / 9683 | Equal | Equal |
| `app/notifications/rain_risk.py` | 4559 / 4559 | Equal | Equal |
| `alembic/versions/0006_rain_delivery_evidence.py` | 1151 / 1151 | Equal | Equal |

Migration SHA256 matches the release plan: `c9ea55b80ac5edea7ad83b4145dded7c932fa52e05575d5d8dbe948d9c99c211`. Git reports LF-to-CRLF conversion warnings for tracked files. Those warnings are not current export mismatches.

These comparisons establish equality of the four Cron source overlays and migration only. They do not establish equality of a whole deployed artifact with HEAD or with the working tree.

Per the existing release record, the minimal API export uses baseline `1af361ada18b7cb854acbfd6124b9d3a9c4af410` plus 0006 and an export-only sanitized `alembic.ini`. Cron uses baseline `70eccf93cf1c7841fb473e0959b0d559032cfa94` plus four runtime overlays, 0006, and sanitized INI. Each export contains 61 allowed files and excludes tests/frontend/release docs. Current HEAD is a different source revision; uncommitted overlays and 0006 are not in HEAD. Therefore Git source at current HEAD is not identical to the whole minimal API deployed export. The proposed source commit also does not recreate that minimal API artifact. Full-artifact hashes and baseline differences remain previous evidence in the release plan; no full-artifact re-audit occurred here. Repository INI stays untouched.

## Previous evidence and pending acceptance

The following evidence is recorded in the release plan/handoff, not newly executed or independently reverified here:

- SQLite/P0 regression: **33 passed**, 7.91s, exit 0.
- Separate local PostgreSQL **16.15** run: **4 passed**, 10.83s, exit 0. Total 37 tests across two runs, not a single run. Both report the existing Starlette multipart `PendingDeprecationWarning`.
- Production API migration to 0006, additive columns/FK, preserved legacy nulls/dedupe, and API/frontend health were verified on 2026-10-10 Bangkok. Cron deployment reached SUCCESS/Ready; deployment success is not scheduled delivery acceptance.
- New Cron scheduled delivery remains pending: normal run **2026-10-11 06:00 Asia/Bangkok**, read-only verification **2026-10-11 06:10 Asia/Bangkok**. Verify actual source linkage and frozen evidence under that separately scheduled task. Old-code delivery on 2026-10-10 does not verify P0-02/P0-03. No manual cron, ingestion, or LINE send is implied.

Actual validation in this preparation task: `git diff --check` passed, exit 0, with only Git's LF-to-CRLF warnings and no whitespace errors. No tests, syntax execution, DB connection, provider request, or production check. Standard `git diff --check` covers tracked changes; it does not validate untracked file contents.

## One proposed coherent commit

Title:
`fix(notifications): correct rain intervals and freeze delivery evidence`

Proposed body:

```text
Interpret hourly rain timestamps as preceding-hour interval ends and use
interval-start local dates consistently in selection and formatting.

Add nullable ForecastRun linkage and versioned frozen rain delivery evidence
through migration 0006. Preserve legacy nulls, daily dedupe, thresholds,
snapshots, history, evaluation, and the 06:00 Bangkok daily alert.

Include scoped regressions, release/handoff records, source overlay review,
and a design-only intraday dependency brief. No intraday implementation.

Previous evidence: 33 SQLite tests passed; separate 4 local PostgreSQL 16.15
tests passed. No tests rerun during source preparation. git diff --check
is the only validation run in this preparation task.

API migration/health previously verified; new cron scheduled delivery
acceptance remains pending 2026-10-11 06:10 Asia/Bangkok verification.
Overlay equality does not imply whole deployed API artifact equality.
```

Explicit-path staging command, **documentation only; not executed**:

```powershell
git add -- app/models/notification.py app/notifications/formatter.py app/notifications/rain_alerts.py app/notifications/rain_risk.py alembic/versions/0006_rain_delivery_evidence.py tests/test_daily_rain_summary.py tests/test_rain_risk.py tests/test_rain_delivery_evidence.py tests/test_rain_evidence_migration.py tests/test_rain_evidence_postgres.py docs/RAILWAY_HANDOFF.md docs/P0_RELEASE_PLAN.md docs/P0_SOURCE_REVIEW.md docs/P1_01_INTRADAY_BRIEF.md
```

The brief belongs in this same source/evidence commit as the documented next task, not as a feature change. No staging/commit/push is authorized here. A source commit does not deploy either exported artifact. Next task follows the P0 scheduled-evidence gate in [P1_01_INTRADAY_BRIEF.md](P1_01_INTRADAY_BRIEF.md).
