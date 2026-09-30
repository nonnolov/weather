# Weather Forecasting System

A real, modular, testable 7-day weather forecasting system.

## Architecture

```
Weather API/NWP → Ingestion → Normalization → PostgreSQL → Forecast → FastAPI
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
| GET | `/api/v1/forecast/{location_id}/runs` | List forecast runs |

## Running Tests

```bash
pytest
# With coverage:
pytest --cov=app --cov-report=term-missing
```

## Weather Providers

Providers are isolated behind a common abstraction (`BaseWeatherProvider`). Each provider normalises its raw API response into standard `NormalizedHourlyForecast` and `NormalizedDailyForecast` objects before storage.

Currently implemented:
- **Open-Meteo** — free, no API key required (default)

To add a new provider, subclass `BaseWeatherProvider` in `app/providers/` and register it in `app/providers/registry.py`.

## Design Principles

- Every forecast retrieval is stored as an immutable historical snapshot — forecasts are never overwritten.
- Provider-specific logic is fully isolated behind the abstraction layer.
- All secrets are loaded from environment variables; no secrets in code.
- Chronological ordering is preserved throughout for future ML evaluation.

## Development Phases

- **Phase 1** ✅ Backend foundation, database, provider abstraction, ingestion, API, tests
- **Phase 2** — Web dashboard (Next.js)
- **Phase 3** — Historical evaluation + accuracy metrics (MAE, RMSE, Bias)
- **Phase 4** — ML bias correction (Linear Regression → XGBoost)
- **Phase 5** — LINE notification service
- **Phase 6** — Testing, security, logging, deployment
