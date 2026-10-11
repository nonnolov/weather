# P4 existing-alert enrichment — 2026-10-11 Asia/Bangkok

## Behavior
Daily rain alerts and intraday updates append one flood-watch paragraph ONLY for a valid rainfall_flood_potential / risk_detected=true / watch assessment from the exact alert forecast run and location. Below-trigger, unsupported scope/provider, missing data or stale forecasts append no flood text. The rain send decision, cooldown, daily dedupe keys, intraday event identity and recipients are preserved. Flood screening does not create an independent send event.

Thai appended text:
⚠️ พยากรณ์ฝนบริเวณนี้เข้าเกณฑ์เฝ้าระวังน้ำท่วมจากฝน ควรติดตามสถานการณ์ โดยเฉพาะจุดระบายน้ำช้า (เป็นการคัดกรองจากฝน ไม่ยืนยันว่าจะเกิดน้ำท่วม)

## Implementation
Shared flood_enrichment module evaluates explicit supplied hourly rows with the P4 evaluator. Intraday delivery reads the full horizon from the SAME persisted source ID, not the newest run; this includes next-day hours omitted from current-day comparator input. Location/run/hour rows use shared read locks under the existing scope transaction. The existing final decision clock is sampled after these reads, then dedupe/replay checks run before rendering. Suppressed decisions do not invoke enrichment.

Daily delivery evaluates its explicit hourly query. Daily/intraday frozen evidence include flood_screening (source ID, location ID, status, rule version, source URL, reason codes, trigger windows, forecast-adaptation basis and calibration limitation). No recipient/GPS is added to that evidence. Formatter deep-copies optional flood evidence so later mutation cannot rewrite the rendered record. LINE's 5000-character limit is enforced.

## Tests
Related final suite: 91 passed, 1 existing python_multipart deprecation warning, no skipped cases. Includes:
- boundary/season/missing-data/stale/source-scope evaluator cases;
- daily mocked sender and exact saved text/dedupe;
- intraday SQLite dry-run using the real source verification/read/formatter path with a mocked lock context;
- actual isolated PostgreSQL 16 preview, mocked acceptance, frozen enrichment and replay suppression;
- existing PostgreSQL intraday source validation, locks, failed/ambiguous sends and acceptance/commit checks.

All sender calls are mocks. No real LINE was sent. PostgreSQL uses a newly initialized temporary loopback cluster on 127.0.0.1:55434 and disposable per-test schemas, separate from application/production data.

## Limits
This remains rainfall screening adapted from observed-rainfall policy, not a calibrated flood probability. Scored historical events remain 0. Named urban scopes outside Bangkok remain unassessed pending reliable profile mapping. See P4_02_RISK_ASSESSMENT_METHOD.md.
Production deployment and enabling actual enriched LINE messages are separate release actions.

Frontend validation: TypeScript noEmit exit 0, ESLint exit 0, Next.js production build exit 0 (static routes generated successfully). No frontend source changes were required for this enrichment step; these checks validate the accumulated P4 UI work before commit.

Final broader regression with isolated PostgreSQL 16: 688 passed, 6 skipped, 18 external-integration cases deselected, 1 existing python_multipart warning; exit 0. The previously failing eight rain-collection cases now execute successfully with the dedicated test URL. Remaining skips require other explicitly configured migration/provenance fixtures. Command: python -m pytest -m 'not integration' -q --show-capture=no with P104_TEST_POSTGRES_URL targeting the temporary loopback cluster. This result validates implementation/regressions, not historical flood prediction accuracy.
