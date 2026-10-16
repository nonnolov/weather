# Admin API Key Security

Updated: 2026-10-17

## What changed

Production maintenance endpoints are now protected by an Admin API Key.

Public read endpoints remain available so the WeatherNow frontend can continue reading locations and forecast data normally.

## Protected production endpoints

The following endpoints require the `X-Admin-API-Key` request header in production:

- `POST /api/v1/locations`
- `POST /api/v1/locations/from-gps`
- `PATCH /api/v1/locations/{location_id}`
- `DELETE /api/v1/locations/{location_id}`
- `POST /api/v1/ingest/{location_id}`

Requests with no Admin API Key or an incorrect key return HTTP 401.

## Public endpoints

Read-only endpoints such as `GET /api/v1/locations` remain public and continue to work normally.

## Key handling

The backend supports an explicit `ADMIN_API_KEY` environment variable.

If `ADMIN_API_KEY` is not configured, the production backend derives a stable Admin API Key from the existing backend `SECRET_KEY` using HMAC-SHA256.

The Admin API Key is never exposed through `NEXT_PUBLIC_*`, frontend JavaScript, or committed credentials.

## Verification

Automated tests verify:

- missing key is rejected
- incorrect key is rejected
- correct key passes the security guard
- public read endpoints remain accessible
- fallback key derivation works when an explicit Admin API Key is not configured

Latest validation:
- focused security/API suite: 26 passed
- related regression suite: 64 passed, 5 skipped
- production `GET /api/v1/locations`: HTTP 200
- production maintenance request without key: HTTP 401
- production maintenance request with wrong key: HTTP 401

## Related commits

- `48c7fff` — security: disable maintenance endpoints in production
- `b7de533` — security: require admin api key in production
