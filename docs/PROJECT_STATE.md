# Weather Forecasting System — Project State

## 1. Project Identity

**Project:** Weather Forecasting System

**Purpose:**
Build a weather forecasting system that provides location-based forecasts, weather risk analysis, and LINE alerts, with the system evolving from fixed seed locations toward user GPS-based forecasting.

**Repository:**

* GitHub: `https://github.com/nonnolov/weather.git`
* GitHub is the current source of truth.
* GitLab is no longer part of the intended development workflow.

---

## 2. Current Git State

**Current branch:**

`phase-1-backend-foundation`

**Current HEAD:**

`202f278 docs: record Railway production handoff`

The branch is synchronized with `origin/phase-1-backend-foundation`. The working tree was clean after the handoff commit was pushed on 2026-10-06.

For current Railway production state and next operational checks, read [RAILWAY_HANDOFF.md](RAILWAY_HANDOFF.md).

### Important Git rule

Preserve any uncommitted user work found in a future session. Inspect `git status` before editing. Do not run destructive cleanup or discard user changes unless explicitly requested.
## 3. Repository / Development Direction

The project is currently developed from GitHub.

Primary repository:

`nonnolov/weather`

Primary branch currently being worked on:

`phase-1-backend-foundation`

Preferred workflow:

```text
Inspect
↓
Make a small scoped change
↓
Run relevant tests
↓
Review git diff
↓
Report results
↓
Commit/push when appropriate
```

Avoid large autonomous repository-wide changes.

---

## 4. Technology Stack

### Backend

* Python
* FastAPI
* Database
* Alembic migrations
* Weather provider abstraction
* Open-Meteo
* Forecast ingestion/services
* LINE Messaging API
* Scheduled alert processing

### Frontend

* Next.js `15.5.9`
* React `19.1.0`
* TypeScript `5.9.2`
* App Router
* Plain CSS
* LIFF SDK `2.31.1`

Known frontend files:

```text
frontend/app/page.tsx
frontend/app/globals.css
frontend/lib/api.ts
```

### Deployment

* Railway — backend and scheduled jobs
* Vercel — frontend
* LINE Official Account / Messaging API
* LINE LIFF

Known intended frontend production domain:

`https://weather-iota-five-83.vercel.app/`

---

## 5. Original Seed Locations

The original system used four initial forecast locations:

1. Chon Buri City
2. Pattaya
3. Si Racha
4. Bang Lamung

These locations were used as initial seed forecast points.

Historical seed data should be preserved.

The scheduler/alert workflow was changed so that the system should no longer continuously refresh and send alerts for these four seed locations.

### Important constraint

Do not delete historical seed data merely to remove scheduler behavior.

Do not break the Accuracy pipeline while changing seed-location behavior.

---

## 6. Current Product Direction

The system is moving toward **user GPS-based weather forecasting**.

Target flow:

```text
User GPS
↓
Latitude / Longitude
↓
Reverse Geocoding
↓
Tambon / Amphoe / Province
↓
Weather Forecast
↓
Risk Analysis
↓
Forecast UI / LINE Alert
```

Example:

```text
ต.แสนสุข
อ.เมืองชลบุรี
จ.ชลบุรี
```

The system should support locations beyond Chon Buri, including Bangkok.

The user's latitude/longitude should be the geographic input used for weather forecasting.

Reverse-geocoded administrative information is intended primarily for:

* displaying the user's location
* identifying the forecast area
* LINE messages
* human-readable context

Do not replace precise coordinates with the administrative name when querying the weather provider.

---

## 7. Weather Provider

Current provider:

`Open-Meteo`

The backend uses a provider abstraction so provider-specific logic should remain isolated from the rest of the application.

Forecast data includes information such as:

* temperature
* precipitation probability
* precipitation amount
* wind
* daily forecast
* multi-day forecast

The frontend is intended to display a 7-day forecast.

---

## 8. Forecast UI Requirements

The UI must work well on:

```text
360px
390px
430px
800px
```

Target devices include:

* mobile
* tablet
* desktop

Requirements:

* No horizontal scrolling
* Temperature is visually prominent
* Rain probability is the second-most prominent weather metric
* Rain amount must be clearly visible
* Forecast should be easy to scan
* Light/dark mode
* Charts or visual future trends where useful
* Avoid presenting the forecast as only text
* Avoid generic AI-generated dashboard styling

Frontend changes should remain scoped to the requested UI task.

---

## 9. Current Frontend Work

The last verified repository inspection on 2026-10-06 found a clean working tree; there were no pending edits to `frontend/app/page.tsx` or `frontend/app/globals.css`.

The earlier frontend redesign and its visual direction remain useful historical context. Verify the live repository before treating any frontend change as pending.
## 10. UI Design Direction

The frontend has been moving toward a distinctive visual system rather than generic AI-generated UI.

Design references/workflows have included:

* Liwan-inspired visual direction
* Hallmark
* Impeccable
* Superdesign as a reference source

Do not blindly copy external designs.

The objective is a deliberate and distinctive Weather UI.

---

## 11. LINE / LIFF

LINE is part of the production workflow.

Known components:

* LINE Official Account
* LINE Messaging API
* LINE LIFF

Known LIFF channel ID:

`2011847040`

The general alert flow is:

```text
Forecast refresh
↓
Risk analysis
↓
Alert generation
↓
LINE message
```

Previously implemented alert capabilities include:

* Risk Score
* Top 2 risk periods
* reverse-geocoded location in messages
* daily deduplication
* production GPS → Forecast → LINE workflow
* date/separator-based alert formatting

A Daily Peak Alert test was previously confirmed working after troubleshooting.

---

## 12. Alert / Scheduler

The current Railway alert service is documented in [RAILWAY_HANDOFF.md](RAILWAY_HANDOFF.md).

Latest verified configuration on 2026-10-06:
- Schedule: `0 23 * * *` UTC (06:00 Asia/Bangkok).
- Start command: `python -m app.notifications.cli`.
- `LINE_CHANNEL_ACCESS_TOKEN` was added to the production cron service without recording its value in Git or chat.
- Deployment `199bc48e-66fc-4237-81ef-96ea2925a2f2` succeeded.
- A successful scheduled alert run has not yet been verified; check the logs after the next scheduled run.

The workflow remains user-location-based. Do not change its logic unless requested.
## 13. Accuracy Pipeline

The project has an Accuracy pipeline for evaluating forecast quality.

The intended architecture is:

```text
Forecast Snapshot
↓
Observation Ingestion
↓
Forecast vs Observation
↓
Accuracy Analysis
```

Relevant concepts include:

* forecast snapshots
* weather observations
* comparison between forecast and observed weather
* historical accuracy evaluation

### Critical rule

Do not break or redesign the Accuracy pipeline while working on unrelated features.

If a task touches:

* forecast snapshots
* observations
* ingestion
* accuracy calculations
* related database models

inspect the existing implementation first and explicitly assess the impact.

---

## 14. Database / Migrations

The backend uses Alembic migrations.

A GPS-related migration has previously been referenced as:

`0004`

The exact migration chain and current database schema must be verified from the repository before making database changes.

The intended location data model includes concepts such as:

```text
latitude
longitude
tambon
amphoe
province
```

Do not assume the exact current schema without inspecting the actual repository.

---

## 15. Testing

The project has used:

* SQLite for regular/local tests
* PostgreSQL integration testing
* Alembic migration testing
* Open-Meteo integration testing

Tests should be distinguished between:

```text
Unit/local tests
Integration tests
Production verification
```

A passing local test does not automatically prove production deployment is working.

---

## 16. Deployment

### Railway

Railway hosts the FastAPI backend, Postgres, and scheduled alert service. Current project/service IDs, live status, database notes, and next verification steps are maintained in [RAILWAY_HANDOFF.md](RAILWAY_HANDOFF.md). Verify live Railway state before making operational changes.

### Vercel

Used for the Next.js frontend.

Known intended production frontend:

`https://weather-iota-five-83.vercel.app/`

### LINE

Used for LIFF, the LINE Messaging API, and weather alerts. Never store token values in this document or in Git.
## 17. Known Historical Production Issue

A scheduled alert run previously crashed because `LINE_CHANNEL_ACCESS_TOKEN` was missing from the new Railway cron service. The user added the variable in Railway Production and the subsequent deployment succeeded on 2026-10-06.

The next scheduled run still needs verification. See [RAILWAY_HANDOFF.md](RAILWAY_HANDOFF.md) for the current deployment ID and follow-up.
## 18. Important Engineering Constraints

Unless explicitly requested:

Do NOT:

* migrate away from FastAPI
* migrate away from Next.js
* replace Open-Meteo
* redesign the entire backend
* redesign the database
* delete historical seed data
* remove the Accuracy pipeline
* replace LINE integration
* introduce Tailwind solely for styling
* perform unrelated cleanup
* perform broad refactors
* change deployment architecture unnecessarily

---

## 19. AI Agent Workflow

### Primary agent

Codex

Codex should be the primary engineering/coding agent for the Weather repository.

### Secondary agent

MiniMax MCode

MCode can be used for:

* secondary investigation
* code review
* small supporting tasks
* assistance when Codex usage is limited

Avoid having multiple agents independently inspect and modify the entire repository for the same task.

Prefer small sequential tasks.

---

## 20. AI Agent Operating Rules

Before editing:

1. Run `git status`.
2. Confirm current branch.
3. Inspect the relevant implementation.
4. Understand dependencies.
5. Identify the exact scope.

During editing:

* Keep changes focused.
* Do not modify unrelated files.
* Do not discard uncommitted work.
* Do not perform broad refactors without authorization.
* Preserve existing APIs and data contracts where possible.

After editing:

1. Run relevant tests.
2. Run typecheck/lint for frontend changes.
3. Review `git diff`.
4. Report changed files.
5. Report test results.
6. Report remaining risks/issues.

---

## 21. Source-of-Truth Hierarchy

When information conflicts, use this order:

```text
1. Current repository files
2. Current git status / git history
3. Current tests
4. Current deployment configuration/state
5. PROJECT_STATE.md
6. Historical chat context
```

This file can become stale.

Always verify important implementation claims against the actual repository.

---

## 22. Current Status

### Verified 2026-10-06

```text
Branch: phase-1-backend-foundation
HEAD: 202f278 docs: record Railway production handoff
Remote: origin/phase-1-backend-foundation
Working tree: clean after push
```

Production operations were documented in [RAILWAY_HANDOFF.md](RAILWAY_HANDOFF.md). That handoff is the current source for Railway database, API, forecast, and alert status. Re-check the repo and Railway before continuing because deployment state can change.
## 23. Handoff Rule

When a new AI agent starts working on this repository:

1. Read this file.
2. Run `git status`.
3. Check the current branch and HEAD.
4. Inspect the relevant source code.
5. Do not assume this file is perfectly current.
6. Preserve uncommitted work.
7. Make only the requested changes.
8. Test and review the diff before reporting completion.

**Most important rule:**

> Inspect first. Do not assume. Do not discard existing work.


## Latest operational update — 2026-10-07

See `docs/RAILWAY_HANDOFF.md` for current production deployment details; older snapshots above may describe superseded accounts or releases.

- Active work branch: `feature/frontend-ux`; source `dffb1f5` adds automatic historical collection for distinct active user current locations.
- Cron Production deployment `7a02bf46-eb46-40f3-babc-5af18a00a1bf`: SUCCESS/Ready; daily 06:00 Asia/Bangkok.
- Morning order: user-location observations (rolling seven completed days), commit, user-location forecast refresh, qualifying LINE alerts.
- Initial private backfill: 4 locations, 672 records with precipitation values; repeat creates zero records; no duplicate groups. Existing seed history retained; seed backfill requires explicit `--scope seeds`.
- Relevant tests: 30 passed, 1 existing warning. API/frontend health checks returned 200.
- Actual new cron execution and LINE delivery remain pending verification. This collection does not automatically train or apply ML.
