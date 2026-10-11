# Remove flood card and LINE note — 2026-10-11 Asia/Bangkok

## Requested behavior
Remove the accumulated-rain/flood-risk card from the dashboard and all flood-watch enrichment from daily and intraday LINE messages. Normal forecast rainfall amounts, period totals, daily totals, peak-hour lines, rain thresholds, cooldown, dedupe, recipient scope and schedule remain part of the existing rain product.

## Implementation
- Dashboard no longer imports/renders FloodRiskCard, so it no longer requests the flood-risk endpoint on a user's page.
- Daily send no longer evaluates flood screening, appends its paragraph or adds flood_screening to new delivery evidence. LINE's 5000-character limit remains enforced.
- Intraday send no longer reads the extra flood snapshot or evaluates screening. The final clock is still sampled after the candidate/source checks before dedupe, rendering or sending.
- Intraday formatter and new frozen evidence no longer accept/include flood evidence.
- Daily-use smoke check follows the new product scope: weather and model PM2.5.
- Regression scenarios use heavy Bangkok rain, the exact saved message, mock sender, frozen evidence and PostgreSQL replay/deduplication. Internal legacy flood calculation/API code remains isolated; it is not rendered or used by LINE.

## Data and release boundaries
No schema migration or delivery/history rewrite. Earlier alerts retain their exact text and evidence. Only future rendered alerts change. The existing P4 API/history are retained for compatibility, not an active dashboard/alert feature. No real LINE test is requested or sent in this release. Existing recipient/live flags are retained.

## Validation and production
See REMOVE_FLOOD_UI_LINE_RELEASE.json for final test counts, frontend build validation, source commit, terminal deployments, public bundle checks and unchanged accepted baseline verification.

Local validation: ================= 215 passed, 1 warning in 354.76s (0:05:54) ==================. Dedicated temporary PostgreSQL stopped after tests. Frontend TypeScript, ESLint and production build all exit 0. No real LINE/provider tests.

Production release: API and daily cron SUCCESS, cron remains build-only at 06:00 Bangkok. Frontend READY and existing production alias promoted after staged bundle/health checks. Public bundle contains PM2.5 and no flood component or flood request. Three deployed alert module hashes match the source commit. Original accepted delivery 7 evidence is unchanged. Stored forecast daily formatting and intraday preview succeed without flood text. Final weather/PM2.5 smoke passed. Existing intraday live policy/one recipient retained. No real LINE test sent.
