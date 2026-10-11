# P4-01 Forecast rainfall exposure and flood-risk assessment

## Status

P4 is in progress. This slice adds a forecast-rainfall exposure report to the API and the active dashboard location. It deliberately returns `assessment_status: not_assessed`; no flood-risk band is assigned.

## Scope

- Read the latest stored hourly forecast for the active location; do not trigger ingestion or write to the database.
- Calculate maximum complete rolling precipitation accumulations over the next 24 fully future hourly intervals for 1, 3, 6 and 24 hour windows.
- Preserve the beginning and ending time of each one-hour precipitation interval and each reported accumulation window.
- Report expected hours, known precipitation hours and complete rolling windows. Missing or invalid amounts remain missing and break any window that depends on them.
- Show model-estimate provenance, retrieval time, and the unassessed status and reasons in Thai/English on the dashboard.
- Do not send LINE, make a warning decision, confirm a flood event or claim measured rainfall.

## Dependencies and risks

- Hourly precipitation follows Open-Meteo's preceding-hour sum convention; the valid timestamp marks the interval end. Each item is represented as `[valid_time - 1 hour, valid_time]`. Source: https://open-meteo.com/en/docs .
- Forecast totals are model output for a grid point, not a rain-gauge observation. They do not represent catchment-wide rainfall or antecedent measured rainfall.
- TMD rainfall categories describe rainfall intensity; they do not alone determine flood effect at a location. TMD defines flood by accumulated water and impacts, and notes prolonged heavy rain and coastal surge as possible causes. Source: https://tmd.go.th/info/การวัดปริมาณน้ำฟ้าหรือหยาดน้ำฟ้า .
- P4-02 follows the clarified requirement to estimate rainfall-driven flood potential at the user's location from forecast rain amount and duration, using area-specific thresholds derived and validated from historical rainfall and flood evidence. The live input is the location's forecast rainfall; historical observations support offline calibration. Do not reuse LINE alert rules or generic rain-intensity labels as flood thresholds. See docs/P4_02_RISK_ASSESSMENT_METHOD.md. P4-03 found candidate HII/GISTDA and BMA evidence sources, but schemas, spatial/temporal matching and validation-ready coverage remain to be checked in docs/P4_03_EVIDENCE_FEASIBILITY.md.

## Tests and acceptance

- Unit tests cover preceding-hour boundaries, exact rolling sums, windows, gaps, missing/negative/non-finite values and lack of usable future data.
- API tests cover latest-run retrieval, active/missing locations, missing forecast, coverage and the explicit unassessed result.
- Frontend acceptance for this slice requires TypeScript typecheck, ESLint and optimized production build. Production UI interaction and deployment are not part of this work.
- P4 cannot be marked complete until local rain/flood evidence is paired, area-specific rain-duration thresholds are validated on held-out events, supported-location coverage and limitations are shown, and user-facing states pass acceptance. The documented method is not yet an operational classifier.

## Local verification

- New focused suite: 7 passed (5 calculation cases and 2 API cases), one existing `python_multipart` deprecation warning.
- Full non-external suite: 517 passed, 128 skipped, 26 deselected, one existing warning. The 26 deselected include 18 marked external integration cases and 8 PostgreSQL-backed P2 collector cases because `PG_URL` is unset in this environment. An unfiltered run reached the same suite but those 8 cases errored during setup for the missing `PG_URL`.
- Frontend TypeScript typecheck and ESLint passed. Optimized Next.js build passed after the card and retrieval-time UI changes.
- `git diff --check` passed. Changes remain uncommitted on `review/p1-intraday-20261010`; no production deployment, LINE send, or production interaction test was performed.

Superseded status update (2026-10-10 UTC): rainfall exposure now feeds the source-backed screening evaluator. Fixed unassessed UI/method labels described above are replaced by three result states. Historical validation still incomplete. See P4_04_SCREENING_IMPLEMENTATION_HANDOFF.md and P4_02_RISK_ASSESSMENT_METHOD.md for current behavior.
