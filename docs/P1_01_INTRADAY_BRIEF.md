# P1-01: read-only intraday design and dependency inspection

Status: user approved preparatory intraday design and LOCAL mocked testing on 2026-10-10 Asia/Bangkok, before scheduled P0 verification. This authorization overrides the earlier start gate only for design/local testing, including the existing isolated delivery/evidence suite; later gate/exclusion wording below does not restrict this preparation. Feature implementation and production activation are not approved. Activation remains gated on reviewed implementation, local tests, and P0 scheduled source-linkage/frozen-evidence acceptance. Planned P0 verification: 2026-10-11 06:10 Asia/Bangkok, after the normal 06:00 daily run. Failure or missing evidence keeps activation gated. Design: [P1_01_INTRADAY_DESIGN.md](P1_01_INTRADAY_DESIGN.md).

## First task and deliverable

Perform a narrow, read-only inspection of existing ingestion, daily alert selection, delivery evidence, and dedupe dependencies. Produce one design note with a dependency map, decision table, unresolved facts, approval choices, and deterministic test specifications. Do not implement alerts or execute production/DB/provider/LINE operations. Any production timing evidence needed later requires separately authorized read-only verification; missing evidence must be marked unknown.

Design goal: compare a fresh forecast's same-location future rain intervals with the most recent successfully delivered forecast for that recipient and location. Use persisted frozen delivery evidence as the baseline, not today's latest source run or an unsent/failed forecast. Here delivery success means LINE API acceptance with durable delivery evidence; handset receipt is unknown. Preserve source links and frozen evidence for any future approved message design.

## Existing dependencies and cadence facts

- Recorded scheduler configuration in [P0_RELEASE_PLAN.md](P0_RELEASE_PLAN.md): `0 23 * * *` UTC, daily 06:00 Bangkok; start `python -m app.notifications.cli`. This is previous configuration evidence, not a fresh live check. Actual start/completion delays and any additional production ingestion cadence are unknown here.
- `app/notifications/cli.py::_main` ingests observations for user locations and commits, then calls `send_user_alerts`. `app/ingestion/service.py::ingest_user_observations` defaults to the seven completed Bangkok days, with idempotent history collection.
- `app/notifications/rain_alerts.py::refresh_and_send_rain_alerts` explicitly fetches a seven-day forecast once per distinct non-null current user location (including browser fallback users), commits each refresh, then calls `send_current_rain_alerts`, which filters LINE recipients before sending. That wrapper refreshes the provider. `send_current_rain_alerts` and `send_rain_alert` alone only consume stored runs; a notification does not automatically refresh the provider. A refresh failure can leave an older stored run selected.
- `send_current_rain_alerts` selects latest stored run by `retrieved_at DESC, id DESC`. `send_rain_alert` requires retrieval on the alert's local date; this is a date check, not an intraday age limit. A forecast from earlier today can still be too old for a future intraday policy.
- `app/api/v1/users.py::refresh_user_forecast` and `app/api/v1/forecasts.py::trigger_ingestion` provide explicit on-demand forecast fetches. Corresponding forecast GET handlers read snapshots. Endpoint availability does not establish invocation frequency or recurring production refresh.
- `app/ingestion/service.py::ingest_forecast_for_location` persists a new immutable `ForecastRun` with hourly/daily records. Existing `app/ingestion/forecasts.py` provides initial missing seed forecasts; Dockerfile default startup includes it. Existing service start overrides must stay unchanged. Initial ingestion is not evidence of recurring intraday cadence.
- `app/notifications/rain_risk.py` supplies interval mapping and current rain selection. `app/models/notification.py`, migration 0006, and `_rain_evidence` supply linked delivery history. `_lock_dedupe_key` and the unique delivery constraint protect daily sends; existing `rain:{location_id}:{local_date}` prevents another same-day delivery. An intraday design needs a distinct approved identity without changing daily dedupe.

There is no verified recurring intraday forecast refresh in this scoped evidence. Design must establish whether existing snapshots arrive frequently enough before proposing an alert trigger. Provider model update timing, scheduler execution timing, and snapshot retrieval timing are separate facts. No new services, dependencies, or cost are allowed.

## Proposed policy questions for approval

All policies below are design proposals, not activated behavior. No final numeric delta, freshness age, cooldown, horizon, or interval-shift limit is chosen here. Use named parameters in the design and obtain explicit approval of values before later implementation.

1. Normalize UTC interval boundaries and location timezone; match the same absolute future intervals in candidate and frozen baseline. Preserve `(t-1h, t]` and local-start-date membership. Propose an explicit rule for an interval already underway; do not prorate hourly rain or label elapsed intervals as future. Missing overlap/data means unknown, not zero rain.
2. Propose significant-change criteria: newly qualifying future rain, material escalation in aligned interval probability (percentage points) or hourly millimeters, and materially earlier onset or shifted windows. Decide whether weakening/disappearance warrants a message. Compare interval values, not daily maxima or whole-day totals; do not treat top-two ranking changes alone as weather changes.
3. Existing **70% OR 10 mm** strong and **30% OR 5 mm** fallback values are rain selection thresholds. They are not automatically significant-change deltas. Separate selection from change magnitude, data completeness, freshness, and the user's remaining future horizon.
4. Propose recipient/location-scoped cooldown based on last durable accepted alert. Define any escalation exception explicitly for approval. Dedupe candidate source identity plus canonical interval/change identity; consider identical-content forecasts with different run IDs and concurrent/replayed evaluation. Daily delivery identity and its 06:00 behavior must remain separate.
5. Advance the baseline only after durable successful delivery. Failed sends, suppressed changes, unsent new runs, and source mutation must not replace it. Document the existing push-before-commit gap; dedupe cannot promise exactly-once handset delivery.

Required edge decisions:

| Case | Proposed treatment to evaluate; approval required |
| --- | --- |
| No successful baseline, legacy null evidence, unsupported evidence version | Skip change notification with an explicit unknown-baseline reason; do not invent a baseline from latest run |
| Stale candidate or missing future values | Skip; propose maximum age and required coverage separately from daily local-date freshness |
| Stale baseline | Decide acceptable baseline age/overlap; skip or establish baseline through an approved delivery path, without automatic sending |
| Same-run replay or identical changed content | Suppress duplicate evaluation/send; baseline and evidence remain unchanged |
| Midnight | Use absolute intervals and local-start-date semantics; date rollover alone is not a significant change; retain cooldown across midnight |
| Location/timezone change | Never compare different locations; determine whether a previous baseline remains valid when returning to a location or its timezone changes |

## Risks and deterministic proposed tests

Risks: insufficient fresh snapshots, provider/model lag, missing interval overlap, daily aggregate confusion, noisy small revisions, baseline loss after location deletion, legacy null evidence, concurrent evaluations, push-before-commit duplicates, and daily/intraday dedupe collisions. Mark stale project-context claims as historical. Do not assume data freshness or actual production timing from scheduler configuration alone.

Specify tests with a fixed clock, synthetic recipient/location identities, frozen evidence, explicit UTC/Bangkok timestamps, and parameterized unapproved policy values. No intraday policy tests are implemented or run in this design task. Parent ran the two existing P0 mocked suites: 12 passed; see design validation evidence. Planned intraday cases:

- Identical data, same-run replay, and different run IDs with identical intervals: no extra alert.
- Significant-change boundary: below/equal/above each proposed delta; selection crossing alone distinguished from approved change criteria.
- New future rain, escalation, earlier onset, ranking-only changes, and weakening: explicit decision/reason for each policy option.
- Missing/stale candidate, absent/legacy/stale baseline, missing overlap, null values, and refresh failure: no invented zero/baseline.
- Midnight-end interval, naive UTC, elapsed/underway intervals, and location/timezone change: correct scope and boundary decisions.
- Cooldown before/at/after proposed boundary, midnight rollover, concurrent replay, failed send/commit: baseline advancement and suppression specified.
- Daily 06:00 delivery and original dedupe remain intact; snapshots, observation history, evaluation timestamps, and prior frozen evidence remain unchanged.

## Acceptance and exclusions

First task passes when one reviewable design note maps every entrypoint above, distinguishes cadence facts from unknowns, and gives a deterministic outcome/reason for every listed edge/test case. It must list policy choices requiring approval, numeric parameters still unset, fresh-data dependency, and reliability limits. Inspection changes zero runtime/test/config/schema files and performs zero ingestion, DB access, provider requests, or LINE sends. P0 scheduled acceptance evidence must be linked before production activation; user explicitly authorized preparatory design/local P0 tests before that result.

Exclude feature implementation, live or unapproved test execution, schedule changes, extra cron/services, packages, paid infrastructure, final numeric settings, migrations, frontend changes, provider polling, ML/evaluation redesign, snapshot/history mutation, outbox redesign, deployment, and automatic activation. Preserve the daily 06:00 alert, current thresholds, hourly end-time semantics, snapshot/history/evaluation pipeline, and source-linked frozen evidence.
