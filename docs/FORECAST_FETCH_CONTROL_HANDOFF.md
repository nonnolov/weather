# Shared forecast acquisition, request budgets and Google adapter

## Result and scope

GPS locations keep their exact coordinates, IDs and recipient assignments. Open-Meteo acquisitions may be shared within a fixed 0.002-degree grid cell only when provider, timezone, administrative scope, requested horizon and local date agree. The representative query point is the cell center, with maximum displacement about 157 m at the equator. Cell boundaries remain separate; this is not district-wide pooling and does not imply identical rainfall at every point.

The four current assigned GPS records (6, 7, 14, 15) map to one acquisition key. No seed rows, location assignments or old forecast snapshots are rewritten. Identical location/time/horizon cache hits reuse that location's existing snapshot; a different location receives a distinct immutable snapshot with the original retrieval timestamp and query provenance.

## Refresh and persistence

All existing ingestion paths call ingest_forecast_for_location. With FORECAST_SHARING_ENABLED=true they acquire through a PostgreSQL advisory lock and a durable cache. Freshness is strictly less than FORECAST_REFRESH_SECONDS (default 3600). Reuse never relabels old data as freshly fetched. A local-date boundary and horizon changes require another acquisition. Provider failures use a 300-second default backoff. No automatic HTTP retry or stale fallback is introduced.

New migration 0009 adds only forecast_fetch_cache and provider_request_budgets. Accepted delivery evidence, recipient/location dedupe and three-hour cooldown remain in their original tables and logic. Existing intraday source-age gates continue to reject stale candidates.

## Request budgets

Reservations commit independently before network requests and survive caller rollback, timeout or provider errors. Planned but unused pages are conservatively counted; this is an upper bound, not a billing invoice. PostgreSQL serialization prevents concurrent workers exceeding a limit. UTC and America/Los_Angeles month/day boundaries are both enforced conservatively.

Google defaults: 9000 monthly / 290 daily requests, bounded by configuration validation. The remaining free-tier margin is not a guarantee: another application on the same Google billing account is outside this ledger. No billing account has been created or changed.

Read-only operator command: python -m app.ingestion.quota_status. Open-Meteo forecast requests are counted without a Google budget cap. Historical observation collectors are separate from this forecast ledger.

## Google: implemented adapter, blocked live production

The provider registry includes google_weather. Its adapter handles explicit hourly intervals, METRIC quantities, all pagination (24 records/page), missing/invalid values, timezone consistency, gaps/duplicates and source attribution. Full local days are aggregated only with complete coverage; today's partial forecast is never labeled a full-day total. Unknown Google conditions are not fabricated into WMO codes. Modeled history is blocked from measured observation ingestion.

Standard Google Weather terms are incompatible with this application's current purpose and durable evidence requirements:
- Weather API section 21.1 restricts weather apps whose primary purpose is providing weather information.
- Hourly forecast caching is limited to one hour, while P1/P2 retain immutable hourly evidence.
Official source: https://cloud.google.com/maps-platform/terms/maps-service-terms
Attribution source: https://developers.google.com/maps/documentation/weather/policies
HTTP contract: https://developers.google.com/maps/documentation/weather/reference/rest/v1/forecast.hours/lookup

Production ingestion of google_weather is unconditionally rejected before HTTP or persistence. Live transient preview additionally requires verified contractual usage rights, GOOGLE_WEATHER_PREVIEW_ENABLED and a server-side API key; all are absent/disabled in production. Setting a boolean is not evidence of usage rights. No Google API request, LINE test, source switch, automatic provider fallback or new paid infrastructure was performed.

Google remains externally blocked until usage rights are established and a compliant retention/notification design is implemented. These code preparations do not mean Google is production-ready or more accurate than Open-Meteo.

## Rollback

Set FORECAST_SHARING_ENABLED=false and redeploy API/daily cron to restore direct acquisition. Keep migration 0009 tables; no destructive production downgrade is needed. Existing snapshots and accepted messages remain unchanged. Google stays blocked.

## Validation

See FORECAST_FETCH_CONTROL_RELEASE.json for final test counts, deployment IDs and production verification.

Validation completed: {'passed': 751, 'skipped': 6, 'deselected': 0} across two independent test groups, with one existing python_multipart warning per process. Dedicated local PostgreSQL concurrency and caller-rollback tests passed. Migration 0009 upgrade/downgrade/upgrade passed against disposable PostgreSQL 16. Earlier runner failures were corrected before this release; the five-minute whole-suite timeout was resolved by split execution. External integration tests were deselected. No real Google/LINE requests in tests.
