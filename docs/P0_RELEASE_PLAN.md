# P0-02/P0-03 release: API and cron deployed; scheduled verification pending

Prepared 2026-10-09T18:05:45.947Z; release execution now authorized. Parent verified production API release on 2026-10-10 Bangkok; cron deployment is terminal SUCCESS; next scheduled execution remains pending.
Source: feature/frontend-ux at fc3d29c5203916a26e3c6c0a33f3712cc263da2e; existing dirty code/tests preserved. Deployment uses reviewed exported baselines + overlays, not a new Git commit. Source commit/push NOT performed; no staging.
This follow-up changes documentation only; no release action, runtime edit, re-audit, or test execution.

## Artifacts and integrity

Full export root: `C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F`.
Manifest outside all build roots: `C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\release-manifest.json`.
Manifest SHA256: `aaa71c35c6790d7744805bd12d421a91bf877dbc54ef204b344e228797b01a37`.
Migration SHA256: `c9ea55b80ac5edea7ad83b4145dded7c932fa52e05575d5d8dbe948d9c99c211`.
- api-schema: `C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\api-schema`; 61 files; full file manifest SHA256 `1d4fcdc046b7d26b1a74bfe92b393ac4d65324ffea7df769a36bf7e054866d0e`.
- alert-cron: `C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\alert-cron`; 61 files; full file manifest SHA256 `b6bdde1d48288cbe76e0e76373a20870a79ff96ecf76ef6c65a11dfdc84c39f8`.
- alert-cron-rollback: `C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\alert-cron-rollback`; 61 files; full file manifest SHA256 `d09d92ba151807503c560ca550947fe19c93c5d193ab1a5ab4b05cb3eb9638b0`.
Candidate hashes cover UTF-8 compact JSON of sorted per-file records (path, origin, SHA256, byte count); they are not archive hashes.
Manifest records every file origin/hash, exact baseline diffsets, source preservation, prior evidence, and the packaging exception.
Superseded: ALL exports/manifests under `C:/Users/NUTCHA~1/AppData/Local/Temp/weather-p0-release-20261009T175931847Z-dad58969`. They remain untouched; NEVER DEPLOY them.

## Scope and byte guarantees

API: Git baseline 1af361ada18b7cb854acbfd6124b9d3a9c4af410 + reviewed 0006 + sanitized alembic.ini ONLY. Exactly two file differences from baseline.
Cron: Git baseline 70eccf93cf1c7841fb473e0959b0d559032cfa94 + four working-tree runtime overlays + 0006 + sanitized alembic.ini. Exactly six differences.
Runtime overlays: app/models/notification.py, app/notifications/formatter.py, app/notifications/rain_alerts.py, app/notifications/rain_risk.py.
Rollback cron: Git baseline 70eccf93cf1c7841fb473e0959b0d559032cfa94 + 0006 + sanitized alembic.ini ONLY. Exactly two differences.
All unchanged files come from baseline Git blobs, including LF bytes. No unchanged working-tree CRLF copies or extra CRLF differences.
Tracked allowlist only: app/**, alembic/**, requirements.txt, pyproject.toml, alembic.ini, Dockerfile, .dockerignore; plus reviewed untracked 0006.
No tests, frontend, Hermes, .env, secrets, caches, Git metadata, or arbitrary untracked files. Each candidate has exactly 61 allowed files.
requirements.txt, pyproject.toml, Dockerfile, .dockerignore and sanitized alembic.ini are byte-identical across all three candidates.
Authorized packaging exception: replace only the exported sqlalchemy.url line with postgresql+psycopg2://localhost/weather_db; no username/password.
Every other INI byte is baseline-identical. Repository alembic.ini remains unchanged. Both services' DATABASE_URL and DATABASE_URL_SYNC were verified valid; all four resolve to the same private DB and override fallback. Values were not printed.
Parent already verified HEAD/backend diff against 70eccf9 is empty. No repeat source audit.

## Minimal API migration and prior validation

API retains deployed runtime, avoiding cron-only ingestion/notification changes. 0006 is self-contained: Alembic op + SQLAlchemy, literal tables, down_revision 0005.
Baseline Alembic env/models support explicit upgrade operations without new ORM fields or autogeneration. Old code tolerates additive nullable fields.
0006 adds nullable forecast_run_id and JSON rain_evidence; FK fk_notification_forecast_run uses ON DELETE SET NULL. No defaults/backfill; dedupe stays.
The original compatibility rationale was static; production API migration verification is recorded below. Cron new-code execution remains unverified.
Prior parent tests: 33 SQLite passed (7.91s), then 4 LOCAL PostgreSQL 16.15 passed (10.83s): 37 tests across TWO runs, not one run.
Both runs have existing starlette multipart PendingDeprecationWarning. No reruns during preparation.

## Authorized release evidence and remaining verification

- Parent evidence dated 2026-10-10 Bangkok: Railway CLI API `deploymentTriggers` queried explicitly for production API and cron. Both returned empty `edges` and `hasNextPage: false`. Repo source `nonnolov/weather` remains; neither service has a connected auto-deploy branch. No GitHub push performed.
- All 183 exported file hashes and immutable release manifest SHA256 reverified; original dirty source preserved.
- Fresh `pg_dump` 18.6 backup: `C:/Users/Nutchanon/Backups/weather/weather-production-before-0006-20261010T030451Z.dump`; 128535 bytes; SHA256 `4783f1142441f70d6d156c04f3463626a595b26a55f39932e1db07329c40be7b`.
- Full restoration to isolated PostgreSQL 18.6 `localhost:55418/weather_restore_0005` passed. All eight archive/restored table counts match: `alembic_version=1`, `daily_forecasts=231`, `forecast_runs=33`, `hourly_forecasts=5544`, `locations=11`, `notification_deliveries=4`, `observations=1224`, `users=5`. Constraints validated; local server stopped. Report: `C:/Users/Nutchanon/Backups/weather/restore-check-20261010T030557Z/restore-report.json`. Backup/recovery required no paid Railway plan, public DB proxy, or new paid service.
- API deployment `339511aa-cb47-4e95-a362-3bd664cba306`: **SUCCESS**. Existing predeploy Alembic logs show `0005 -> 0006` at `2026-10-10T03:08:24Z`. Production revision `0006` confirmed; nullable integer `forecast_run_id`, nullable JSON `rain_evidence`, FK `ON DELETE SET NULL`, and unchanged `uq_notification_dedupe` verified. All four legacy deliveries retain both new fields NULL; forecast runs 33 and observations 1224 unchanged. API seed logs: 0 created, 4 skipped.
- Post-release API `/health`, `/api/v1/locations`, `/api/v1/forecast/1` and frontend `/api/backend/health`: HTTP 200, valid JSON. No manual ingestion, LINE, or cron run.
- Cron deployment `6ffccaae-5764-47cf-89c9-c5e2d39b5287` terminal SUCCESS; live state Ready verified after release. Start `python -m app.notifications.cli`, restart NEVER, and schedule `0 23 * * *` UTC (06:00 Bangkok) unchanged; no cron predeploy, staged changes, issues, or recent failures. New scheduled delivery is still UNVERIFIED.
- Follow-up scheduled: one-time read-only verification on 2026-10-11 at 06:10 Asia/Bangkok, after the normal 06:00 cron. Verify actual ForecastRun linkage/frozen evidence; no manual cron, ingestion, LINE, or production mutation. Production release is deployed; delivery end-to-end acceptance remains pending.
- Remaining: verify the next normal scheduled run on **2026-10-11 at 06:00 Bangkok** using read-only logs/aggregate linkage and evidence counts. The 2026-10-10 06:04 Bangkok scheduled run succeeded on old code; it does not verify this release. No manual cron, ingestion, or LINE. LINE API acceptance does not prove handset receipt.

Historical pre-release read-only Railway evidence dated 2026-10-10 Bangkok; exact check time unavailable: prior API/cron SUCCESS, no staged changes/issues. This described old deployments, not production verification of new code.
Project: 71e0e499-6a9d-46c5-a552-b9a9da0e1928; environment: 7ca11e27-30cd-4217-a80d-0b1647cb55c9.
API: 89478e29-e136-4a39-9ace-3dc128d01495; prior deployment 600785e7-98bc-4e6e-ab48-59a813d75497.
Cron: 7b46c113-c416-4571-ae05-7b697b4da7ec; prior deployment 174bdfbc-b1e1-465a-945f-ceabd8d630e0 (SUCCESS/buildOnly is not scheduled delivery proof).
Existing API start: `sh -c 'python -m app.seeds.locations && exec uvicorn app.main:app --host 0.0.0.0 --port 8000'`.
Dockerfile default CMD ingests. Enforce unchanged existing start overrides; do not fall back to Dockerfile CMD.

## Railway CLI templates ? REVIEW ONLY; DO NOT EXECUTE

Historical templates; API deployment and cron submission are recorded above. Syntax was checked in previous preparation. These upload/deploy commands are documentation only, not read-only operations; do not rerun during this documentation task.
```powershell
$env:RAILWAY_CALLER = "skill:use-railway@1.3.5"
$env:RAILWAY_AGENT_SESSION = "weather-p0-release-20261010"
# API: historical approved release command; deployment SUCCESS recorded above.
railway up 'C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\api-schema' --path-as-root --project 71e0e499-6a9d-46c5-a552-b9a9da0e1928 --environment 7ca11e27-30cd-4217-a80d-0b1647cb55c9 --service 89478e29-e136-4a39-9ace-3dc128d01495 --detach -m "P0 API schema 0006"
# Cron: only after terminal API SUCCESS, schema 0006 and stable health.
railway up 'C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\alert-cron' --path-as-root --project 71e0e499-6a9d-46c5-a552-b9a9da0e1928 --environment 7ca11e27-30cd-4217-a80d-0b1647cb55c9 --service 7b46c113-c416-4571-ae05-7b697b4da7ec --detach -m "P0 rain interval and delivery evidence"
# Prepared cron rollback: only under separate rollback authorization.
railway up 'C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\alert-cron-rollback' --path-as-root --project 71e0e499-6a9d-46c5-a552-b9a9da0e1928 --environment 7ca11e27-30cd-4217-a80d-0b1647cb55c9 --service 7b46c113-c416-4571-ae05-7b697b4da7ec --detach -m "P0 rollback cron retaining schema 0006"
```

## Rollback and remaining risks

Rollback cron uses prepared old runtime + 0006 + sanitized INI, retaining start/schedule and additive DB columns. No destructive downgrade.
After 0006, retain API migration-only candidate. Original API image lacks 0006; predeploy upgrade head cannot resolve the DB revision. Do not revert to that original image.
Backup/recovery and API release are verified above. Source commit/push NOT performed. Cron terminal SUCCESS verified; next scheduled execution remains pending verification. Prepared cron rollback remains available; no rollback executed.
Known risks remain: send-before-DB-commit can lose evidence or permit retry duplicates; location deletion still cascades delivery deletion.

Parent package review: independently verified all 183 file hashes against the manifest, exact 2/6/2 baseline diffsets, credential-free exported INI, and Python syntax for all candidates; passed. No package or runtime source changed during this review.
