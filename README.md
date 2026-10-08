# Weather Forecasting System

A real, modular, testable 7-day weather forecasting system.

## Architecture

```
Weather API/NWP â†’ Ingestion â†’ Normalization â†’ PostgreSQL â†’ Forecast â†’ FastAPI
```

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic v2, PostgreSQL, Alembic
- **Testing**: pytest, pytest-asyncio, httpx

## Project Structure

```
app/
  api/          # FastAPI routers
  core/         # Config, database session
  models/       # SQLAlchemy ORM models
  schemas/      # Pydantic schemas
  providers/    # Weather provider abstraction + implementations
  ingestion/    # Forecast ingestion service
alembic/        # Database migrations
tests/          # pytest test suite
frontend/       # Next.js dashboard
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 14+

### 2. Environment

```bash
cp .env.example .env
# Edit .env with your database URL and provider API keys
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

## Observation Ingestion

Historical Open-Meteo observations feed stored forecast evaluation. Seed locations once, then run the operational CLI for a completed date range:

```bash
python -m app.seeds.locations
python -m app.ingestion.observations --start-date 2024-06-01 --end-date 2024-06-07
```

Without dates, it ingests previous local calendar day for each seeded Chon Buri location. Re-running same range inserts no duplicate `(location_id, observed_at)` rows.

## Frontend

The frontend is a standalone Next.js application. Start the API first, then:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local`
to the FastAPI base URL if it is not running at `http://localhost:8000`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/locations` | List all locations |
| POST | `/api/v1/locations` | Create a location |
| GET | `/api/v1/locations/{location_id}` | Get a location |
| POST | `/api/v1/ingest/{location_id}` | Trigger forecast ingestion |
| GET | `/api/v1/forecast/{location_id}` | Get latest forecast |
| GET | `/api/v1/forecast/{location_id}/evaluation` | Evaluate stored hourly forecasts against matching observations |
| GET | `/api/v1/forecast/{location_id}/runs` | List forecast runs |
| GET | `/api/v1/forecast/{location_id}/corrected` | Get held-out-validated temperature correction |

## Running Tests

```bash
pytest
# With coverage:
pytest --cov=app --cov-report=term-missing
```

## Weather Providers

Providers are isolated behind a common abstraction (`BaseWeatherProvider`). Each provider normalises its raw API response into standard `NormalizedHourlyForecast` and `NormalizedDailyForecast` objects before storage.

Currently implemented:
- **Open-Meteo** â€” free, no API key required (default)

To add a new provider, subclass `BaseWeatherProvider` in `app/providers/` and register it in `app/providers/registry.py`.

## Design Principles

- Every forecast retrieval is stored as an immutable historical snapshot â€” forecasts are never overwritten.
- Provider-specific logic is fully isolated behind the abstraction layer.
- All secrets are loaded from environment variables; no secrets in code.
- Chronological ordering is preserved throughout for future ML evaluation.

## Forecast Accuracy Data Integrity

The production forecast-evaluation pipeline must pass the read-only data-integrity checks before accuracy metrics are treated as trustworthy. See [`docs/FORECAST_ACCURACY_DATA_INTEGRITY.md`](docs/FORECAST_ACCURACY_DATA_INTEGRITY.md) for the daily checklist and implementation priorities.

## Development Phases

- **Phase 1** âœ… Backend foundation, database, provider abstraction, ingestion, API, tests
- **Phase 2** âœ… Web dashboard (Next.js)
- **Phase 3** âœ… Historical evaluation + observation ingestion + accuracy metrics
- **Phase 4** âœ… ML temperature bias correction with chronological holdout
- **Phase 5** âœ… LINE notification service with DB deduplication
- **Phase 6** âœ… Testing, security, logging, container deployment

## LINE Notifications

Set `LINE_CHANNEL_ACCESS_TOKEN` and comma-separated `LINE_USER_IDS`, then run:

```bash
python -m app.notifications.cli
```

Alerts use LINE Messaging API push messages and deduplicate by stored delivery key.

## Docker Deployment

```bash
docker compose up --build
```

Production requires a non-default `SECRET_KEY`, `DEBUG=false`, and explicit `CORS_ORIGINS`.

## Personalized GPS Forecast MVP

Users can send browser GPS coordinates to `POST /api/v1/users/{external_user_id}/location/from-gps`. The API reverse-geocodes the coordinates into province, district, and subdistrict, stores the coordinates and administrative area, and binds the user to that Location.

User-specific forecast endpoints:

- `GET /api/v1/users/{external_user_id}/forecast` — latest forecast for the user's current Location.
- `POST /api/v1/users/{external_user_id}/forecast/refresh` — fetch a fresh forecast using that Location's stored coordinates.

For LINE delivery, `external_user_id` is intended to be the LINE user ID when LINE Login/webhook identity is used. `python -m app.notifications.cli` now targets each registered user's current Location instead of broadcasting one seed forecast to every recipient. The previous seed-alert implementation remains available as an internal test utility.

The web dashboard's primary flow is `Use my location`: browser GPS ? reverse geocoding ? user/location binding ? personalized 7-day forecast. If GPS is unavailable, the four Chon Buri seed locations remain available as a test fallback.


## LINE LIFF Identity

The dashboard supports optional LIFF authentication. When NEXT_PUBLIC_LIFF_ID is configured, the browser initializes LIFF, obtains the raw ID token, and sends it to POST /api/v1/line/auth. The backend verifies the token with LINE and uses the verified `sub` as the user's `external_user_id`. A local browser ID remains available when LIFF is not configured.

Required environment variables:

    LINE_LOGIN_CHANNEL_ID=<LINE Login channel ID>
    NEXT_PUBLIC_LIFF_ID=<LIFF ID>
    NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

LINE setup:
1. Create or use a LINE Login channel in the LINE Developers Console.
2. Add a LIFF app to that channel.
3. Set the LIFF Endpoint URL to the deployed frontend URL.
4. Enable the `openid` scope for the LIFF app.
5. Put the resulting LIFF ID in `NEXT_PUBLIC_LIFF_ID`.
6. Put the LINE Login channel ID in `LINE_LOGIN_CHANNEL_ID`.

The backend verifies the ID token with LINE; the frontend does not treat a browser-supplied user ID as authenticated identity.
