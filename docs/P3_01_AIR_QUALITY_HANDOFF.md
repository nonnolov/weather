# P3-01 PM2.5 and air quality

## Scope and dependencies

User authorized proceeding with the recommended rain-contract review and P3 while P2 collects evidence. This task implements a separate air-quality adapter/API and bilingual card in the existing dashboard. It uses existing HTTPX/FastAPI/Next dependencies, location records, the API and Vercel project. No new infrastructure, paid plan, database table, notification rule or recipient is required.

The source is Open-Meteo's CAMS Global model, explicitly selected with domains=cams_global. Source documentation: https://open-meteo.com/en/docs/air-quality-api . This is a roughly 45 km model grid with 3-hour native data, exposed as hourly output. It is not an at-point measurement. The card identifies both Open-Meteo and CAMS, and distinguishes valid time from retrieval time; model run time is unavailable and stays null.

European AQI is read directly from the provider and labeled as European, not Thai. It is the provider's consolidated pollutant index, not a PM2.5-only conversion. Upper bounds 20/40/60/80/100 map to good/fair/moderate/poor/very poor; above 100 is extremely poor. PM2.5 units are micrograms per cubic metre. Do not apply Thai 24-hour PM2.5 thresholds to this instantaneous output.

## Implementation and risks

GET /api/v1/air-quality/{location_id} requires an existing active location and performs no database writes, weather refresh, LINE call or scheduled job. Invalid IDs return 404. Epoch timestamps are requested with GMT and converted to aware UTC; units, aligned monotonically increasing hourly timestamps and array lengths are checked before use. Negative/non-finite/non-numeric values remain missing, never zero.

A 128-location per-process cache retains data for ten minutes and serializes provider calls. Failures also have a ten-minute retry interval. On refresh failure, prior same-location data are explicitly stale; absent data are unavailable. Timeout/body limits are 8-second HTTP, 10-second fetch, 12-second total cache/service wait and 64 KiB decoded body. Redirects and environment proxies are disabled. Provider error text/coordinate URLs are not returned. This bounds one API process, not a distributed quota; separate replicas have independent caches.

The current value must not be future-dated and must be under two hours old; beyond one hour it is stale. Retrieval age beyond one hour is also stale. Missing current values do not become future values. The next 24 hours retain null gaps, and the UI displays a trend only with at least two known PM2.5 values. A screen-reader-accessible table accompanies the decorative bars. Switching location aborts old requests and uses a new component identity. Air-quality failures do not block weather data.

## Tests and acceptance

New cases cover AQI boundaries, null/negative/NaN/infinite values, units, UTC/epoch and malformed timelines, current/future/stale/missing states, concurrent cache requests, cache eviction and expiry, cached failure/coordinate isolation, cancellation lock release, mocked HTTP failures/body limits, active/inactive/missing API locations and response provenance. A separate real provider request using public Bangkok coordinates passed schema/unit/timestamp parsing.

Acceptance requires isolated regression, frontend typecheck/lint/build, a deployed API with verified code, READY frontend, and production proxy/UI checks. Completion results are recorded after verification. The phase does not claim measured accuracy or add PM2.5 LINE alerts.

## P2 contract review

Additional public-source review on 2026-10-11 Asia/Bangkok found the official standard /Rainfall contract requires interval metadata, but it is a different API from the legacy rain_24h_graph feed. It cannot establish that feed's timezone/accumulation semantics. The existing collection therefore remains quarantined; endpoint alignment, point-aligned measured reference and numerical baseline stay open. No provider was contacted and no inference was promoted to verified evidence.

## Rollback

Revert this additive API/UI release while retaining schema 0008 and station history. No migration downgrade is needed. Existing P1 flags, allowlist, forecast snapshots and cron schedule are preserved. Continue P2 collection independently.

## Completed local verification

Full credential-isolated and external-network-blocked suite: 646 passed, 18 external integration cases deselected, one existing python_multipart warning, 662.93 seconds, exit 0. New air-quality suite contributes 41 cases; targeted air-quality/forecast/health run passed 51 cases. Frontend dependencies were installed from the unchanged lockfile with scripts disabled; TypeScript, ESLint and Next production build all exited 0. Original 34 protected files, branch/HEAD and index remain unchanged. Frontend baseline text matches the original current UI (four physical hash differences are line endings only). Production release remains pending at this checkpoint.
