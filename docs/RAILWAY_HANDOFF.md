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
