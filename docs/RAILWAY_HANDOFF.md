# Weather Railway Handoff

Last updated: 2026-10-10 Asia/Bangkok

This is the current operational handoff. Verify live Railway state before acting because deployments and secrets can change.

## P0-02/P0-03 authorized release: API and cron deployed; scheduled verification pending (2026-10-10 Bangkok)

- Release execution authorized. Deployment uses reviewed exported baselines + overlays, not a new Git commit. Source commit/push NOT performed; no staging or GitHub push. Existing dirty code/tests preserved. This follow-up changes only documentation; no runtime edits, tests, re-audit, or release actions.
- Railway CLI API `deploymentTriggers` queried explicitly for production API and cron: both empty `edges`, `hasNextPage: false`. Repo source `nonnolov/weather` remains; neither has a connected auto-deploy branch.
- All 183 exported file hashes and immutable manifest SHA256 reverified. Artifact paths, hashes and exact baseline differences remain in [P0_RELEASE_PLAN.md](P0_RELEASE_PLAN.md).
- Fresh `pg_dump` 18.6 backup: `C:/Users/Nutchanon/Backups/weather/weather-production-before-0006-20261010T030451Z.dump` (128535 bytes), SHA256 `4783f1142441f70d6d156c04f3463626a595b26a55f39932e1db07329c40be7b`. Full restoration to isolated PostgreSQL 18.6 `localhost:55418/weather_restore_0005` passed; constraints validated. Archive/restored counts match all eight tables: `alembic_version=1`, `daily_forecasts=231`, `forecast_runs=33`, `hourly_forecasts=5544`, `locations=11`, `notification_deliveries=4`, `observations=1224`, `users=5`. Local server stopped. Report: `C:/Users/Nutchanon/Backups/weather/restore-check-20261010T030557Z/restore-report.json`. No paid Railway plan, public DB proxy, or new paid services needed.
- Both services' `DATABASE_URL` and `DATABASE_URL_SYNC` verified valid; all four resolve to the same private DB. Values not printed.
- API deployment `339511aa-cb47-4e95-a362-3bd664cba306` **SUCCESS**. Alembic logs: `0005 -> 0006` at `2026-10-10T03:08:24Z`. Production revision `0006`, nullable integer `forecast_run_id`, nullable JSON `rain_evidence`, FK `ON DELETE SET NULL`, and unchanged `uq_notification_dedupe` verified. Four legacy deliveries preserved with both fields NULL; forecast runs 33/observations 1224 unchanged. Seed logs: 0 created, 4 skipped.
- API `/health`, `/api/v1/locations`, `/api/v1/forecast/1` and frontend `/api/backend/health`: HTTP 200, valid JSON. No manual ingestion, LINE, or cron run.
- Cron deployment `6ffccaae-5764-47cf-89c9-c5e2d39b5287` terminal SUCCESS; live state Ready verified after release. Start `python -m app.notifications.cli`, restart NEVER, and schedule `0 23 * * *` UTC (06:00 Bangkok) unchanged; no cron predeploy, staged changes, issues, or recent failures. New scheduled delivery is still UNVERIFIED.
- Follow-up scheduled: one-time read-only verification on 2026-10-11 at 06:10 Asia/Bangkok, after the normal 06:00 cron. Verify actual ForecastRun linkage/frozen evidence; no manual cron, ingestion, LINE, or production mutation. Production release is deployed; delivery end-to-end acceptance remains pending.
- Rollback constraint: retain additive `0006`; do not revert to the old API image missing `0006`. Prepared cron old code + `0006` remains available; no rollback executed. Known send-before-DB-commit and location-cascade risks unchanged.

The sections below preserve historical evidence. Their preparation-only/no-authorization statements describe those earlier tasks; current release status is above.

## Historical local P0-02 pending release

- Local, uncommitted change on `feature/frontend-ux`; no deployment, cron run, ingestion, database access, or LINE message.
- Open-Meteo hourly precipitation and precipitation probability at `t` now select and label rain interval `(t-1h, t]`; stored `valid_time` and forecast snapshots remain unchanged.
- Hourly rain intervals belong to local date containing interval start. A Bangkok interval ending at local midnight belongs to previous local day. Provider daily records remain assigned by stored `forecast_date`.
- Unit coverage adds naive-UTC incident timestamp, Bangkok conversion, midnight boundary, grouped-period boundaries, daily peak, formatter daily aggregate, and existing delivery regression checks.
- Deferred: frontend hourly display semantics. P0-02 adds no UI change or intraday scheduler.
- Source reviewed. Unit tests passed: `& C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -m pytest -q tests/test_rain_risk.py tests/test_daily_rain_summary.py tests/test_rain_alert_delivery.py tests/test_notifications.py` — 23 passed, 1 warning in 1.46s, exit 0. Existing warning: `starlette` `PendingDeprecationWarning` importing `multipart`.
- Production not verified. No commit or deploy.

## Historical local P0-03 review; local PostgreSQL 16.15 verified (2026-10-10)

- Uncommitted implementation only; `feature/frontend-ux` remains at `fc3d29c5203916a26e3c6c0a33f3712cc263da2e`. No commit, push, deployment, Railway operation, production DB access, ingestion, restart, real LINE message, dependency installation, or persistent environment change.
- P0-03 files: `app/models/notification.py`, new `alembic/versions/0006_rain_delivery_evidence.py`, additive evidence code in `app/notifications/rain_alerts.py`, new `tests/test_rain_delivery_evidence.py`, new `tests/test_rain_evidence_migration.py`, new `tests/test_rain_evidence_postgres.py`, and this handoff section. The preceding P0-02 section and all existing P0-02 changes are preserved; formatter/risk logic and their tests are not P0-03 changes.
- Small additive schema: nullable `forecast_run_id` FK with `ON DELETE SET NULL`, plus nullable JSON `rain_evidence`. No defaults or historical backfill. Existing and non-rain deliveries remain null/unknown. ForecastRun deletion retains delivery evidence and its original source ID; existing location deletion still cascades delivery deletion and is outside this scope.
- Actual rain send freezes the supplied run's provider, retrieval timestamp, nullable model run timestamp, local alert date/timezone, schema/template/selection versions, mode (`strong_rain`, `daily_peak`, `below_threshold_daily_summary`), score-ranked selected periods, today's hourly interval boundaries/probability/precipitation, separate daily aggregates, and exact formatted message text. UTC ISO timestamps normalize SQLite's naive UTC values. Missing model run time remains null. No latest-run re-query, recipient duplication, GPS, credentials, or raw provider metadata in evidence. Exact message text retains the already-displayed location name.
- Evidence is built before the network await and attached to a delivery only after a successful push. Existing recipient/location/day dedupe, skip/failure/retry behavior, thresholds, scoring, freshness, P0-02 preceding-hour mapping, wording, snapshots, observation/evaluation history, and 06:00 schedule remain unchanged.
- New regression checks cover replay from frozen evidence after source/latest changes, all three modes, daily-versus-period probability, midnight interval mapping, selected top periods, missing daily aggregates, UTC location, skip paths, failed push/retry, and legacy null provenance. The migration check uses a temporary SQLite file, explicit safe URLs, and disables Alembic's `load_dotenv`; it checks actual 0005-to-0006 upgrade, legacy preservation, invalid FK rejection, source deletion survival, downgrade, and re-upgrade without backfill. Parent executed these checks successfully as part of the suite below.
- Parent reviewed the scoped code, migration, and tests and approves the implementation. Parent then used the existing installed interpreter through an authorized Remote Desktop terminal with process-only `DATABASE_URL=sqlite+aiosqlite:///:memory:` and `DATABASE_URL_SYNC=sqlite:///:memory:`, restoring the prior process environment afterwards. Actual command:

  ```powershell
  & C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -m pytest -q tests/test_rain_risk.py tests/test_daily_rain_summary.py tests/test_rain_alert_delivery.py tests/test_notifications.py tests/test_rain_delivery_evidence.py tests/test_rain_evidence_migration.py
  ```

  Actual result: **33 collected, 33 passed**, 1 existing `starlette` multipart `PendingDeprecationWarning`, in **7.91s**, exit 0. This includes real SQLite upgrade/downgrade/re-upgrade, legacy-null preservation without backfill, FK deletion preservation, all three delivery modes, mocked failure, skip, and dedupe. No production database was accessed or real LINE message sent.
- Parent inspected `tests/test_rain_evidence_postgres.py` for isolation and cleanup, then executed `pytest.main(['-q', '-s', 'tests/test_rain_evidence_postgres.py'])` using the existing Python 3.12 interpreter. `P003_TEST_POSTGRES_URL` came from the local URL in `alembic.ini`, remained in process memory, and was asserted to use loopback. Before pytest imports, `DATABASE_URL` and `DATABASE_URL_SYNC` were set to in-memory SQLite URLs. Safe command template (replace only the local PostgreSQL placeholder; never record credentials):

  ```powershell
  @'
  import os
  import sys
  from urllib.parse import urlsplit

  os.environ["P003_TEST_POSTGRES_URL"] = "<LOCAL_POSTGRES_URL>"
  assert urlsplit(os.environ["P003_TEST_POSTGRES_URL"]).hostname in {"localhost", "127.0.0.1", "::1"}
  os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
  os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"

  import pytest
  sys.exit(pytest.main(['-q', '-s', 'tests/test_rain_evidence_postgres.py']))
  '@ | & C:\Users\Nutchanon\AppData\Local\Programs\Python\Python312\python.exe -
  ```

  Actual result: **PostgreSQL 16.15**, Alembic `PostgresqlImpl` with transactional DDL; **4 collected, 4 passed**, 1 existing `starlette` multipart `PendingDeprecationWarning`, in **10.83s**, exit 0. Tests exercised real upgrade to `0005` then `0006`, downgrade to `0005` and re-upgrade to `0006`, legacy nulls without backfill, invalid FK rejection within a SAVEPOINT, unique dedupe, and `ON DELETE SET NULL` preserving frozen evidence. Three-mode regression verified the exact supplied run, source mutations, and dedupe. Parent SELECT queries of schema names before and after confirmed zero new `weather_p003_test_` schemas remained. No production connections, real LINE messages, or writes to existing schemas/tables occurred. The prior **33-pass** SQLite/P0-02/P0-03 regression result remains unchanged; this documentation follow-up reran no tests.
- Historical note: the initial sandbox CLI attempt failed before collection (`CommandNotFoundException`; interpreter access returned `Access is denied`). Subsequent parent executions resolve local SQLite and PostgreSQL verification. **LOCAL PostgreSQL 16.15 is verified; Railway staging, target release, and live behavior remain UNVERIFIED.**
- Production release prerequisite: local PostgreSQL verification is complete; Railway staging was not tested and no release approval is implied. Before deploying code that maps the new columns, apply reviewed Alembic revision `0006` to the release database under separate authorization. Revision `0006` must precede the new code. Old code can continue using the additive schema; do not deploy new code against schema `0005`.
- Rollback: prefer reverting application code while retaining the additive columns. Downgrading `0006` removes all recorded evidence and source links irreversibly without a backup; downgrade the application first. SQLite batch migration reconstructs the delivery table, so review lock/rebuild behavior separately from PostgreSQL ALTER TABLE behavior.
- Remaining issues: existing LINE send-before-DB-commit gap remains. A push can succeed while flush/commit fails, leaving no durable history and allowing retry duplicates; success here means API acceptance, not handset receipt. No outbox/reliability redesign or DB-enforced write-once policy was added. Evidence is a frozen snapshot, not a tamper-proof ledger. Location deletion still removes delivery history. Parent review and local SQLite/PostgreSQL verification are complete; scoped test code is approved by review, not for release. Railway target release and live behavior remain UNVERIFIED. Next: separately authorized production migration `0006` before new code, followed by target release and live verification; no release approval is implied.

## Repository

- GitHub: `nonnolov/weather`
- Working branch: `phase-1-backend-foundation`
- HEAD before this handoff update: `fd1b831 chore: finalize Hermes GitHub bootstrap`
- Working tree was clean before this file was added.
- No application source code was changed during the Railway work described below.

## Production Railway

- Project: `weather` (`71e0e499-6a9d-46c5-a552-b9a9da0e1928`)
- Environment: `production` (`7ca11e27-30cd-4217-a80d-0b1647cb55c9`)
- Postgres service: `Postgres` (`f60aba17-30cd-4bfb-a6e6-084b70c61aa7`), healthy; 500 MB volume remains attached.
- API service: `weather-api` (`89478e29-e136-4a39-9ace-3dc128d01495`), latest observed deployment `60d52075-54e5-4b21-8241-fd4675afd9ae`, SUCCESS.
- API URL: https://weather-api-production-9152.up.railway.app

## Database and forecast state

The old Postgres database was not migrated, modified, or deleted. The active plan changed to rebuilding what can be regenerated on the new database. Do not resume a database migration unless requested.

The API deployment ran Alembic migrations and the location seed. Production has the four seed locations: Chon Buri City, Pattaya, Si Racha, and Bang Lamung. On 2026-10-06, fresh Open-Meteo forecasts were requested through the production ingestion API:

| Location ID | Forecast run ID | Hourly rows | Daily rows |
| --- | ---: | ---: | ---: |
| 1 | 5 | 168 | 7 |
| 2 | 6 | 168 | 7 |
| 3 | 7 | 168 | 7 |
| 4 | 8 | 168 | 7 |

Verified after ingestion: `GET /api/v1/locations` returned 4 locations; `GET /api/v1/forecast/1..4` returned each latest run with 7 days, 168 hourly rows and 7 daily rows; `GET /health` returned `ok`.

Legacy user accounts, preferences, LINE user IDs, and historical user-specific data were not restored. Whether the new database currently has alert recipients has not been verified.

## LINE alert cron

- Service: `weather-alert-cron` (`7b46c113-c416-4571-ae05-7b697b4da7ec`)
- Schedule: `0 23 * * *` UTC = 06:00 Asia/Bangkok.
- Start command: `python -m app.notifications.cli`.
- The failure was a missing `LINE_CHANNEL_ACCESS_TOKEN` environment variable.
- The user added that variable in Railway Production. Its name is present on the cron service; its value is secret and is intentionally not recorded or retrieved.
- Latest deployment after adding it: `199bc48e-66fc-4237-81ef-96ea2925a2f2`, SUCCESS; no staged changes remain.
- A successful scheduled alert run has not yet been confirmed. Check Railway cron logs after the next scheduled run (2026-10-07 around 06:00 Asia/Bangkok). Confirm exit status and LINE send result. If the token is rejected, ask the user to replace it in Railway without sending it in chat.
- The old cron errors in logs are from before the variable was configured.

## Follow-up

1. After the next cron schedule, inspect the latest cron deployment and logs.
2. Confirm whether any eligible LINE users exist in the new database; user-specific records were not migrated.
3. If no eligible recipients exist, the user must register/link LINE accounts in the new production system before end-to-end alert delivery can be verified.
4. Keep all secret values, database URLs, and tokens out of this file, Git history, and chat.

## Handoff maintenance

After each Weather project task, update this file with the work completed, verification, and remaining next step. Never record secret values. Commit and push this handoff with the scoped project changes when the user asks to keep the work available across account changes.

## Frontend GPS request failure (2026-10-06)

The production frontend's `/api/backend/health` and `/api/backend/api/v1/locations` returned 404 while the new Railway API `/health` returned 200. `frontend/next.config.ts` still used the previous Railway API URL as its fallback.

- Updated the rewrite fallback to `https://weather-api-production-9152.up.railway.app`.
- Updated Vercel project `weather` in scope `weather-9c1f`, Production `API_BASE_URL`, to the same new API URL. This is a public URL, not a secret.
- Preserved the GPS flow: save the user's GPS location, refresh that user's forecast, then retrieve it. No cron logic changed.
- Ignored Vercel local metadata, environment files, and TypeScript build cache; kept `.env.example` available as a tracked template.
- Local verification: `npm.cmd run typecheck` and `node node_modules/next/dist/bin/next build` both exited 0.
- Production verification: Vercel deployment `dpl_EpHggStPB6VNAmce7kNaEn883fvz` was Ready. Through the stable frontend URL, `/api/backend/health`, `/api/backend/api/v1/locations`, and `/api/backend/api/v1/forecast/1` all returned 200. The GPS POST route was checked using an empty invalid body (expected 422), without creating a test user or location. Real browser GPS/LINE flow still requires a user retry.


## Frontend UI/UX improvement (2026-10-06)

The user confirmed the production GPS forecast works after the API proxy fix.

- Work branch: `feature/frontend-ux`, based on `1af361a`.
- Added a focused welcome screen and prominent GPS action, permission explanation, three loading phases, specific GPS errors and retries.
- Location and forecast are displayed together only after successful loading, preventing stale data from being labelled with a new location.
- Sample forecasts are available in a collapsible selector containing only the four seed areas. Selecting a sample does not update the user's saved location.
- Added a six-hour temperature/rain outlook; improved responsive seven-day rows, long location labels, focus targets and reduced-motion support. Thai/English and light/dark controls remain available.
- API, LINE authentication and the user-location-only alert cron logic are unchanged.
- ESLint excludes generated `next-env.d.ts` and uses a named config export.
- Verification: TypeScript and production build passed. ESLint passed after excluding the generated file. Live preview verification follows after pushing this feature branch.
- Production rollout remains pending review of this frontend change.

### UI preview verification

- Feature implementation commit: `848bd3c`; pushed to `origin/feature/frontend-ux`.
- Final TypeScript and ESLint checks passed. Vercel preview build is Ready (`dpl_DYoobBGyFnJPbqPtBf9SZTcbJvoi`, 41 seconds), confirming the final source builds on Vercel.
- Preview: https://weather-ckmsetfyz-weather-9c1f.vercel.app
- Branch alias: https://weather-git-feature-frontend-ux-weather-9c1f.vercel.app
- Browser inspection reached Vercel SSO, which returned `FUNCTION_INVOCATION_FAILED`. Visual, live sample-loading, language/theme and mobile browser checks remain unverified. Deployment protection was not changed.
- Next step: review the preview using an authorized Vercel session, then approve merging the UI branch into the production branch. Production frontend has not been updated with these UI changes.

## Illustrated frontend design (2026-10-06, evening)

The user requested an elegant frontend with illustrations and authorized implementation.

- Continued on `feature/frontend-ux`.
- Added `frontend/app/WeatherArtwork.tsx`: lightweight decorative SVG illustrations for clear, cloudy, rainy, stormy, snowy and foggy forecasts. Text remains the accessible weather description; no new image service or dependency.
- Reworked the welcome composition, forecast hero, hourly strip and daily cards with a cream/navy palette, subtle borders/shadows, larger rounded corners and dark-theme colors.
- Mobile uses a horizontally scrollable hourly strip, two-column metrics and stacked charts/daily rows. Safe-area spacing remains supported.
- Preserved GPS/API/LINE flows and existing user-location-only cron logic.
- No production deployment is authorized by this design change; preview review is still required.
- Previous preview access remains blocked by Vercel SSO errors. Do not claim live browser or mobile verification until those checks succeed.

Verification for the illustrated design: `npm.cmd run typecheck`, `npm.cmd run lint`, `next build` and `git diff --check` all passed. Build route `/` is 10.8 kB with 113 kB first-load JS. This confirms compilation, not live visual behavior.

Illustrated UI implementation commit: `c148b93`, pushed. Vercel deployment `dpl_3JxgFbjtKxQovPPPjycMDhB5jD8e` is Ready after a 41-second build. Review URL: https://weather-badl5l0pc-weather-9c1f.vercel.app . Production is unchanged; visual review remains pending Vercel preview access.

## Pre-cron readiness audit (2026-10-06, before midnight)

- Railway plugin verified new Production: API, Postgres and Hermes Online; cron Ready with schedule `0 23 * * *`; no recent failures. No successful scheduled delivery has yet been demonstrated.
- API service lacks `LINE_LOGIN_CHANNEL_ID`. A deliberate invalid-token request returned HTTP 503, "LINE Login channel is not configured." This is a confirmed blocker to LIFF identity verification, even though browser GPS forecasts work.
- Prepared a staged API-only addition of `LINE_LOGIN_CHANNEL_ID` using the non-secret channel ID `2011847040` recorded in PROJECT_STATE. This has NOT been applied or deployed. Confirm it is the current LINE Login channel before applying; applying requires explicit production deploy authorization.
- Recipient count and current-location bindings remain unknown. Windows Railway CLI is logged into the OLD account and lists only `victorious-learning`; attempts to query new-project DB variables were denied. SSH also lacks a local key. Do not query the old database or create public access to work around this.
- Source inspection: observations CLI and alert CLI call `ingest_seed_observations`, which ingests ONLY the four active seed locations. GPS user locations do not automatically receive observations through this path. User-only forecast refresh/send behavior remains unchanged.
- Read-only archive probe for seed Chon Buri, 2026-10-05, with the current requested variables returned HTTP 200 and 24 hourly timestamps. Timestamp count does NOT prove every weather variable is non-null. Historical data are provider model/reanalysis output, not local station truth.
- Protected UI preview `weather-badl5l0pc-weather-9c1f.vercel.app`: authenticated `vercel curl` verified health and forecast/1 HTTP 200. CLI generated its protection access credential internally; its value was not displayed or committed. Deployment protection remains enabled. Browser/mobile visual checks remain pending.
- Next: apply the reviewed API LINE Login configuration after deploy approval; log Windows CLI into the new Railway account outside chat; run aggregate read-only recipient/observation checks. Then decide explicitly whether to extend observation ingestion to user locations without changing the ordered 06:00 workflow.

## Windows Railway CLI account corrected (2026-10-06, late evening)

The user completed Railway CLI browser login to the new account. `railway list --json` now exposes project `weather` (`71e0e499-6a9d-46c5-a552-b9a9da0e1928`) and Production. The Windows repository was linked to this project/environment and `weather-api`.

Aggregate DB audit still cannot run: Postgres has no public DATABASE_PUBLIC_URL, and private `railway connect --tunnel-only` requires a local SSH key, which is absent. No TCP proxy, SSH key, schema change or production deploy was created. The staged LINE Login Channel ID change remains pending. Next database check should use private SSH/tunnel access, with only aggregate counts returned and no recipient IDs or coordinates in logs.

## LINE configuration deployed and private readiness verified (2026-10-07, shortly after midnight)

The user explicitly authorized completing the LINE deploy, SSH setup and post-06:00 verification.

- Applied ONLY the staged API LINE_LOGIN_CHANNEL_ID change. Deployment `600785e7-98bc-4e6e-ab48-59a813d75497` is SUCCESS/Online. An invalid-token auth probe now returns expected 401 instead of 503. This proves the missing configuration is resolved, not a real user's LINE login.
- Created a dedicated Ed25519 SSH key on Windows at `C:\Users\Nutchanon\.ssh\weather_railway_ed25519`, restricted the private file ACL to Nutchanon, and registered its public key as `weather-railway-PC`. No key contents are in this repository.
- Native Windows OpenSSH binaries failed; Git's OpenSSH client works. Generated the dedicated config at `C:\Users\Nutchanon\.ssh\weather_railway_config` with alias `weather-api-railway`. Railway host key was accepted on the first connection and recorded; changed known host keys remain rejected.
- Private SSH into the API container executed an aggregate DB query in a READ ONLY transaction. No public TCP proxy or DB tunnel was needed; no data was modified.
- Verified counts: 3 users, all 3 with current locations; 3 distinct user locations; 0 LINE recipient candidates (the application's U-prefix criterion); 0 LINE candidates with forecasts; 0 notification deliveries.
- Observations: 96 rows; latest timestamp 2026-10-05 16:00 UTC; 0 observations for the user current locations.
- User action required for real delivery: open the production LIFF frontend via the intended LINE account, finish normal LINE sign-in, then use GPS again to bind that verified identity to a location. Browser fallback accounts do not receive LINE pushes. Do not fabricate recipient IDs, transfer browser identities blindly, or send unsolicited test messages.
- Created a one-time ChatGPT automation to check the cron execution/logs on 2026-10-07 at 06:10 Asia/Bangkok and report the outcome in Thai without sensitive values. Scheduled execution is pending; no 06:00 success is claimed yet.
- Cron logic and frontend production deployment were not changed. Accuracy for GPS still needs an explicitly scoped observation-ingestion extension.

## Illustrated frontend released to Production (2026-10-07)

The user explicitly authorized deploying the new frontend to Production.

- Released frontend source from commit `1f4b0ed` on `feature/frontend-ux` (illustrated UI implementation `c148b93`).
- Target: Vercel team `weather-9c1f`, project `weather` (`prj_K6LybtzdJhZhL4ajYrD0755JRJGV`), Production environment.
- First direct frontend-directory CLI build failed because the project expects Root Directory `frontend`. Automatic approval review rejected uploading the entire repository root because that could include unrelated backend files. Resolved safely by exporting ONLY tracked `frontend/` files into an isolated release directory; no backend, local secrets, node_modules or local .next outputs were uploaded.
- Production build passed TypeScript, lint and Next.js compilation. Staged deployment `dpl_9WRFsLA3XhcG5HGWk5uzUYQQ2pmH`, https://weather-eyw5u4hg3-weather-9c1f.vercel.app , was promoted after root/health/forecast checks returned HTTP 200.
- Stable production URL: https://weather-iota-five-83.vercel.app
- Post-promotion verification: stable root, `/api/backend/health`, `/api/backend/api/v1/locations`, `/api/backend/api/v1/forecast/1` all HTTP 200. Root HTML contains the new welcome UI and weather artwork. This is HTTP/source verification; real GPS/LINE browser and mobile visual checks are still user verification.
- No backend deployment, schema change, LINE message or cron change was part of this frontend release.
- Active development remains `feature/frontend-ux`. The older `phase-1-backend-foundation` branch has not yet incorporated this UI branch; do not release its older frontend without deliberately merging the new UI first.

## Frontend Thai heading update (2026-10-07)

User requested changing the Thai heading to “อากาศวันนี้ ใกล้คุณ”. Updated only that title in `frontend/app/page.tsx`; English heading and application logic are unchanged. Releasing the tracked frontend-only source to Vercel Production using the established isolated export workflow. Deployment verification follows below.

Heading release verified: source commit `d4623d9`; Production deployment `dpl_8upPfzYLB59Gu49WYEnWWHsKEMbs` passed build/typecheck/lint and was promoted. Stable frontend returned HTTP 200, with the requested new Thai heading present and the previous heading absent.

## LINE recipient registration verified (2026-10-07, 00:36 Asia/Bangkok)

Following the user's mobile LINE login/GPS retry, a private read-only aggregate DB audit found 5 users, 5 with current locations, 4 distinct current locations, and **1 LINE recipient candidate with a stored forecast**. This is up from zero before the retry. No LINE ID or coordinates were retrieved or recorded. Notification delivery count remains zero; no test push was sent. Data prerequisites for one LINE recipient are now present; actual delivery still depends on OA friendship/unblocked status, valid Messaging API credentials, qualifying rain conditions and the scheduled cron execution. User-location observation rows remain zero (seed observations total 96).


## Automatic user-location history (2026-10-07)

User authorized finishing automatic historical collection for user locations.

- Added ingest_user_observations: distinct active User.current_location_id values, shared locations fetched once; unused seeds are not automatically collected. Retry seven completed Bangkok dates through yesterday; retain existing history and insert unique location/timestamp rows.
- Provider errors and invalid timestamps are counted per location. Other locations and subsequent forecast/alerts continue. Database errors remain fatal. Forecast targets, rain thresholds and LINE deduplication are unchanged.
- Alert CLI collects this scope and commits before refresh/send. Manual observations CLI defaults to users; --scope seeds remains available.
- Regression validation: 30 passed, 1 existing python_multipart warning. Covers unique/active locations, idempotency, provider failure, rolling dates, empty scope, invalid dates and commit-before-alert ordering, plus existing ingestion/evaluation/correction/notification tests.
- Private provider probe: 4 distinct current user locations, 672 hourly records; all have precipitation and temperature values; no empty hours or provider failures.
- Executed reviewed ingestion source through private API SSH without changing container files or sending notifications: first pass created 672, second created 0; 672 user observations with rain values; zero duplicate groups. Existing 96 seed rows retained. No schema change, public proxy or secret output.
- Source commit dffb1f5 pushed to feature/frontend-ux. Preparing a tracked-backend-only cron release. Record deployment outcome below before claiming automatic production collection ready.
- Active branch remains feature/frontend-ux; do not release the older phase-1 branch without merging current work. Historical data are provider model/reanalysis output, not station truth. Matching forecast/observation timestamps and future scheduled execution remain necessary for accuracy validation.


Production release verified: cron deployment `7a02bf46-eb46-40f3-babc-5af18a00a1bf` is SUCCESS/Ready, no pending work and zero recent failures. Uploaded only tracked backend files from source commit dffb1f5 (release snapshot HEAD 0fa714f); no frontend, Hermes workspace or local secret files. Start command and daily 06:00 Bangkok schedule retained. There are no runtime logs yet: actual scheduled execution is still pending and will be checked by the existing 06:10 verification automation.

Post-release HTTP checks: API /health, /api/v1/locations and /api/v1/forecast/1, plus frontend /api/backend/health, all returned 200. API/frontend were not redeployed by this task. README encoding/line endings were repaired in 36bf7b7; final documentation now describes user history and explicit seed-only backfill.


## Daily LINE rain messages — 2026-10-07

User approved both previously proposed templates and requested exact below-threshold wording “พยากรณ์ฝนยังไม่ถึงเกณฑ์” without “แจ้งเตือน”.

- Cron now sends a rain warning when existing strong-risk or daily-peak fallback criteria qualify; otherwise it sends a daily rain summary. Existing thresholds and user-location targets are retained.
- Rain heading: “🌧️ แจ้งเตือนฝนวันนี้”; qualifying line: “มีโอกาสฝนถึงเกณฑ์แจ้งเตือน”; below-threshold heading: “🌤️ สรุปฝนวันนี้”; exact line: “พยากรณ์ฝนยังไม่ถึงเกณฑ์”.
- Both include location display name, Thai calendar date, available maximum rain probability, full-day precipitation total, advice, actual stored forecast retrieval time, and the production frontend link. Risk time windows appear only for qualifying rain. Full-day totals use today's daily record, or a complete 24-hour sum; missing values are omitted.
- Stale forecasts, absent rain data and incomplete below-threshold evidence are skipped, never presented as a clear-day result. Existing recipient/location/day rain dedupe key is shared across both templates. Failed LINE pushes do not create a success record.
- Expanded cron logs show send/skip/failure and forecast refresh/failure counts without sensitive recipient or coordinate values.
- Validation: 30 relevant tests passed with 1 existing python_multipart warning. Covers both templates, original daily-peak fallback, daily deduplication, stale/missing/partial data, failed-push retry, location-local dates and actual update time, alongside existing rain risk and user-observation pipeline tests.
- Preparing a backend-only deployment to weather-alert-cron; no manual real LINE push was invoked. Record source/deployment verification below.


Daily-message release verified: source `70eccf9` pushed to `feature/frontend-ux`; backend-only cron deployment `174bdfbc-b1e1-465a-945f-ceabd8d630e0` is SUCCESS. Start command remains `python -m app.notifications.cli` and schedule `0 23 * * *` UTC (06:00 Bangkok). API health returned 200. No real LINE test message was sent; first scheduled use of these templates remains pending 06:00 execution.


## Authorized real LINE template test — 2026-10-07

User explicitly requested sending both message conditions to registered logged-in users. A private read-only user/location query found 1 active bound LINE recipient. Sent two clearly labeled test messages using the production formatter from source 70eccf9: qualifying rain (sample 80%, 12 mm, 14:00–17:00) and below threshold (sample 20%, 0.5 mm). Both begin “🧪 ข้อความทดสอบ — ข้อมูลฝนตัวอย่าง ไม่ใช่พยากรณ์จริง”. LINE Messaging API accepted both requests with HTTP 200; zero failures. API acceptance does not prove handset receipt or reading. No notification delivery/dedupe record, forecast write or cron invocation was made, preserving the scheduled 06:00 delivery. Credentials stayed in process memory and were not printed or stored in source. Recipient identifiers and coordinates were not exposed.


## Historical P0-02/P0-03 packages: preparation only (2026-10-09T18:05:45.947Z)

- Complete exports: `C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F`. API-schema, alert-cron and alert-cron-rollback: **61 files each**.
- Manifest: `C:\Users\NUTCHA~1\AppData\Local\Temp\weather-p0-release-ready-20261009T180542728Z-vkIr3F\release-manifest.json`; SHA256 `aaa71c35c6790d7744805bd12d421a91bf877dbc54ef204b344e228797b01a37`. Exact candidate paths/hashes and review-only CLI templates: [P0_RELEASE_PLAN.md](P0_RELEASE_PLAN.md).
- API baseline 1af361a + 0006 + sanitized INI: two differences. Cron baseline 70eccf9 + four approved runtime overlays + 0006 + sanitized INI: six differences. Rollback 70eccf9 + 0006 + sanitized INI: two differences. All unchanged files use Git blob bytes; no CRLF extras. Build/dependency bytes match all three.
- Authorized export-only exception: sqlalchemy.url = postgresql+psycopg2://localhost/weather_db; every other INI byte unchanged. Repository alembic.ini untouched. Require DATABASE_URL and DATABASE_URL_SYNC on both services at preflight.
- ALL original roots/manifests under `C:/Users/NUTCHA~1/AppData/Local/Temp/weather-p0-release-20261009T175931847Z-dad58969` are superseded, retained, incomplete; NEVER DEPLOY.
- Existing P0 code/tests/dirty tree retained. No stage, commit, push, deploy, configuration/DB/LINE operation, installation, re-audit, or test rerun. Prior 33 SQLite + 4 LOCAL PostgreSQL 16.15 passed across two runs; no production new-code verification.
- Release gates remain: separate source commit approval; branch/watch/autodeploy push safety; fresh live/schema check (old 0005 evidence from P0-01); verified backup/recovery; required DB environment variables; unchanged start/predeploy overrides. These do not block package completeness.
- Order: API existing predeploy alembic upgrade head; terminal SUCCESS/schema 0006/health; then cron terminal SUCCESS. Preserve python -m app.notifications.cli and 0 23 * * * UTC (daily 06:00 Bangkok). No manual cron or LINE; read-only evidence checks after normal scheduled delivery only.
- Keep additive columns during prepared cron rollback. Do not downgrade DB or redeploy original API missing 0006. Send-before-commit and location-cascade risks remain.
