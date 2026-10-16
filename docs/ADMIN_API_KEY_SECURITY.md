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

## Production rate limiting

Rate limiting is also enabled on abuse-prone production actions.

| Action | Limit |
| --- | ---: |
| Audience visit registration | 60 requests/minute/IP |
| LINE authentication | 20 requests/minute/IP |
| GPS / reverse geocoding | 12 requests/minute/IP |
| Forecast refresh | 6 requests/minute/IP |
| LINE onboarding / subscription actions | 20 requests/minute/IP |
| Admin maintenance actions | 30 requests/minute/IP |

When a client exceeds a limit, the API returns HTTP 429 Too Many Requests and includes a `Retry-After` header.

Production uses Railway's `X-Real-IP` header as the primary client identifier. Public read endpoints and `/health` are not rate limited by this application layer.

The current limiter stores counters in the running API process. This matches the current single-replica production deployment. If the API is scaled to multiple replicas later, the counters should move to a shared store such as Redis or to a shared edge rate-limit layer.

Full rate-limit documentation is available in `docs/RATE_LIMIT_SECURITY.md`.

## Verification

Automated tests verify:

- missing Admin API Key is rejected
- incorrect Admin API Key is rejected
- correct Admin API Key passes the security guard
- public read endpoints remain accessible
- fallback key derivation works when an explicit Admin API Key is not configured
- rate-limit buckets are isolated by action and client
- requests over the configured limit return HTTP 429
- `Retry-After` is included on limited responses
- Railway `X-Real-IP` is used for production client identification

Latest validation:
- focused Rate Limit + Admin/API suite: 29 passed
- LINE / User / Audience suite: 69 passed
- production `GET /api/v1/locations`: HTTP 200
- production maintenance request without key: HTTP 401
- production maintenance request with wrong key: HTTP 401
- production Admin maintenance request #30 within one minute: HTTP 401
- production Admin maintenance request #31 within one minute: HTTP 429 with `Retry-After`

## Related commits

- `48c7fff` — security: disable maintenance endpoints in production
- `b7de533` — security: require admin api key in production
- `9e1463a` — security: add production rate limits
