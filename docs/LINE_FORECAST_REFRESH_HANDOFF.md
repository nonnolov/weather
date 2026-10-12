# LINE forecast refresh repair — 2026-10-12 Asia/Bangkok

## Production symptom and evidence
The user completed LINE login, friendship and notification-area setup. At 22:00–22:01 Bangkok, location writes and onboarding status returned HTTP 200. The frontend then requested GET /api/v1/line/forecast/refresh, which returned 405; reading the uncreated forecast returned 404. No provider forecast request occurred in that failing path.

## Change
Send POST for the protected forecast refresh endpoint, as required by app/api/v1/line_onboarding.py. Keep the authenticated token and existing location/forecast recovery behavior. The browser signup QA now requires POST and the Bearer token and returns the real endpoint's 201 status, rather than accepting any HTTP method.

## Validation and rollout
Production build passed typecheck, compile and lint. Browser signup QA and deployment results are recorded in LINE_FORECAST_REFRESH_RELEASE.json after verification. The change only requires a frontend deployment. API and cron deployments, explicit consent requirements and paused daily/intraday delivery remain unchanged.

The real user must retry Use location after opening the updated Dashboard. Successful real provider refresh and explicit notification consent are separate remaining acceptance steps; mocked browser tests do not prove either.
