# Production Rate Limiting

Updated: 2026-10-17

WeatherNow applies application-level sliding-window rate limits to abuse-prone endpoints in production.

## Limits

| Action | Limit |
| --- | ---: |
| Audience visit registration | 60 requests/minute/IP |
| LINE authentication | 20 requests/minute/IP |
| GPS/reverse-geocoding actions | 12 requests/minute/IP |
| Forecast refresh actions | 6 requests/minute/IP |
| LINE onboarding/subscription actions | 20 requests/minute/IP |
| Admin maintenance actions | 30 requests/minute/IP |

When a client exceeds a limit, the API returns HTTP 429 with a Retry-After header.

## Client identification

Production requests use Railway's X-Real-IP header as the primary client identifier. Local/test traffic falls back to request.client.host.

## Protected actions

Rate limiting covers:
- POST /api/v1/audience/visit
- POST /api/v1/line/auth
- LINE onboarding status/subscription actions that call LINE services
- GPS location resolution endpoints
- user and LINE forecast refresh endpoints
- admin location create/update/delete endpoints
- admin forecast ingestion

Public forecast/location reads and /health are not rate limited by this layer.

## Implementation note

The limiter is in-process and is appropriate for the current single-replica weather-api deployment. If weather-api is scaled to multiple replicas, move rate-limit counters to a shared store such as Redis or enforce the limit at a shared edge layer so all replicas use the same counters.
