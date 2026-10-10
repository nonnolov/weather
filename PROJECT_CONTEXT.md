# Weather Forecasting System — Project Context

## Initial implementation status (legacy numbering)
- Phase 1 Backend Foundation: COMPLETE
- Phase 2 Dashboard: COMPLETE
- Phase 3 Evaluation + Observation Ingestion: COMPLETE
- Phase 4 ML bias correction: COMPLETE
- Phase 5 LINE notifications: COMPLETE
- Phase 6 hardening + container deployment: COMPLETE

## Stack
FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, Pydantic v2, Next.js/TypeScript/Tailwind, Open-Meteo.

## Seed locations
1. Chon Buri City — `chon-buri-city` — 13.3611, 100.9847
2. Pattaya — `pattaya` — 12.9236, 100.8825
3. Si Racha — `si-racha` — 13.1736, 100.9170
4. Bang Lamung — `bang-lamung` — 12.9500, 100.8833
All use `Asia/Bangkok` and remain evaluation/alert seed locations.

## Forecast/evaluation
Forecast snapshots are immutable `ForecastRun` records. Evaluation matches exact location + valid/observed timestamp and calculates MAE, RMSE, Bias by horizon.

## Observation ingestion
Historical Open-Meteo observations persist into `observations`. Ingestion is idempotent at `(location_id, observed_at)` in both service logic and DB constraint migration `0002`. CLI: `python -m app.ingestion.observations --start-date YYYY-MM-DD --end-date YYYY-MM-DD`.

## Phase 4 ML
Local temperature bias correction only. Linear regression uses chronological train/test split. Future observations are excluded from training. Correction is selected only when held-out MAE improves baseline. Baseline remains fallback. XGBoost is optional and not required by current environment.
API: `GET /api/v1/forecast/{location_id}/corrected?variable=temperature_2m`.

## Phase 5 LINE
Uses LINE Messaging API push endpoint with Bearer channel access token. Credentials come only from environment variables. `NotificationDelivery` provides DB-backed deduplication. CLI: `python -m app.notifications.cli`.
Required env: `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_USER_IDS`. Optional `LINE_API_BASE_URL`.
No webhook/chatbot implemented.

## Phase 6
- Production CORS from `CORS_ORIGINS`.
- Production rejects default `SECRET_KEY` and `DEBUG=true`.
- Request logging with `X-Request-ID`.
- Dockerfile + Docker Compose + `.dockerignore`.
- Alembic migrations through `0003`.
- Secrets excluded from images and source.

## Verification
Latest local full suite: 83 passed, 17 skipped, 2 warnings before Phase 6 hardening. Notification suite: 3 passed. Re-run full pytest after final hardening.

## Git rules
Do not commit or push unless explicitly requested. Keep `.env`, `.venv`, caches, and credentials out of Git.


## Current P0-P7 work

Follow docs/MASTER_ROADMAP.md for the current user-defined phase sequence. P1 is deployed with an open natural positive intraday LINE verification gate. P2 is in progress: P2-01 adds a read-only provenance/interval audit, archive request isolation and populated metric API fixes. No at-point accuracy percentage or validated correction improvement is claimed. See docs/P2_01_EVALUATION_HANDOFF.md for tests, data evidence and remaining work.


P2-03 adds durable hourly station staging and a read-only collection status API. P2 accuracy acceptance is still open because the legacy feed's time contract is not authoritatively confirmed. See docs/P2_03_AUTOMATIC_COLLECTION_HANDOFF.md for the release/rollback record. This rollout targets the existing API only; station data remain separate from current-point observations and LINE logic.


P3-01: separate PM2.5/model air-quality API and bilingual dashboard card implemented. Source Open-Meteo/CAMS Global; European AQI explicitly labeled, epoch/GMT times, missing/stale handling and a bounded cache. See docs/P3_01_AIR_QUALITY_HANDOFF.md (P3_01_AIR_QUALITY_HANDOFF.md from docs). P2 remains active in quarantine with its reference-alignment and numerical-baseline gates open. P1 natural positive acceptance/handset verification remains open. Production release verified; see docs/P3_01_PRODUCTION_RELEASE.json.
