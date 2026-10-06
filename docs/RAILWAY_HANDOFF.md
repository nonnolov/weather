# Weather Railway Handoff

Last updated: 2026-10-06 22:15 Asia/Bangkok

This is the current operational handoff. Verify live Railway state before acting because deployments and secrets can change.

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
