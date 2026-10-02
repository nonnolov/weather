# Weather Forecasting System — Project Context

## Project
Weather forecasting system for Chon Buri Province.
Backend: FastAPI + SQLAlchemy + PostgreSQL + Alembic.
Frontend: Next.js + TypeScript + Tailwind CSS.
Provider: Open-Meteo.
Repository: fynn-group/weather
Main working branch: phase-1-backend-foundation

## Current status
Phase 1 — Backend Foundation: COMPLETE
Phase 2 — Frontend Foundation + Dashboard: COMPLETE
Phase 3 — Forecast Evaluation: IMPLEMENTED
Phase 3 — Observation Ingestion: NEXT TASK
Phase 4 — ML: NOT STARTED

Latest commit:
9bbde97 feat: add forecast evaluation

Latest Phase 3 test result:
3 passed, 2 warnings

## Seed locations
Initial forecast/evaluation locations only:

1. Chon Buri City
   slug: chon-buri-city
   latitude: 13.3611
   longitude: 100.9847
   timezone: Asia/Bangkok

2. Pattaya
   slug: pattaya
   latitude: 12.9236
   longitude: 100.8825
   timezone: Asia/Bangkok

3. Si Racha
   slug: si-racha
   latitude: 13.1736
   longitude: 100.9170
   timezone: Asia/Bangkok

4. Bang Lamung
   slug: bang-lamung
   latitude: 12.9500
   longitude: 100.8833
   timezone: Asia/Bangkok

These are seed/evaluation locations. Do not remove or replace them.

## Forecast architecture
Open-Meteo forecast is the baseline provider.

The system stores forecast snapshots instead of overwriting previous forecasts.

Main flow:

Weather provider
→ ingestion
→ PostgreSQL
→ forecast snapshots
→ evaluation against observations
→ later ML bias correction

ML must not replace the baseline blindly.
Future ML should only improve local bias/correction and must be compared against the baseline.

## Phase 3 Evaluation
Implemented evaluation engine:

- matches forecast and observation by location and exact valid/observed timestamp
- calculates forecast horizon from retrieval time to valid time
- MAE
- RMSE
- Bias
- error definition: forecast - observation
- groups results by variable and forecast horizon
- ignores missing/non-finite values
- deterministic/testable metric logic

Evaluation API:

GET /api/v1/forecast/{location_id}/evaluation

Current limitation:
There is not yet enough real historical observation data in the database, so production evaluation metrics may currently be empty.

## Next task: Observation Ingestion
Implement Observation Ingestion only.

Requirements:

- reuse the existing Observation model
- reuse existing provider abstraction and Open-Meteo integration
- ingest real observation data
- support the four seeded locations
- persist observations to PostgreSQL
- make ingestion idempotent for the same location + observation timestamp
- do not create duplicate observations
- store values required by the existing evaluation engine
- add focused tests with controlled mocks/fixtures
- unit tests must not call the real external API

Do NOT:
- implement ML
- implement LINE notifications
- change forecast behavior
- add authentication
- start Phase 4
- perform unrelated refactoring
- create unnecessary dependencies
- commit or push automatically

## User-location forecasting
Future feature idea:
Allow a browser user to grant geolocation permission and request a forecast using the user's latitude/longitude.

This is NOT part of the current Observation Ingestion task.

Keep the four seeded locations for evaluation.

## Git rules
Do not commit or push unless explicitly requested.

Before any commit:
1. run relevant tests
2. inspect git diff
3. inspect git status
4. ensure .env, .venv, and __pycache__ are not committed

## Agent workflow
Use small focused tasks.
Do not perform broad repository-wide analysis unless necessary.
Do not modify unrelated files.
Do not implement future phases.
After completing a task, report:
- files changed
- tests run
- test results
- limitations