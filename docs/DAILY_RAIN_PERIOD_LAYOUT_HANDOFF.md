# Daily rain LINE period layout

Date: 2026-10-11 (Asia/Bangkok)

## Result

Daily qualifying rain alerts now use the user-approved Thai layout: short separators, chronological caution periods, maximum hourly rain probability in each period, total forecast rain in that period, maximum hourly rain, whole-day total, umbrella advice, uncertainty statement, actual forecast update time, and the existing details URL.

All numbers come from the supplied persisted forecast run. No example values are hardcoded. A period probability is the maximum hourly probability, not the probability of rain over the entire window. The total includes every hourly interval inside the displayed window, including quieter bridging hours. Precipitation at t represents the preceding hour (t-1h, t]; midnight-ending intervals are included in the preceding local day.

Missing, invalid, or conflicting duplicate hourly values produce "ข้อมูลไม่ครบ" for the affected metric. Identical duplicates are counted once. Hourly fallback for a daily total requires full, unique coverage of the local day. An available valid provider daily aggregate remains the preferred whole-day total. Display amounts use up to two decimals, with aggregation before rounding.

Below-threshold daily summaries retain their current text. Existing selection thresholds, schedule, recipient configuration, daily dedupe and intraday cooldown are unchanged. P4 enrichment continues to append its flood-watch sentence only for a qualifying assessment.

Qualifying daily evidence uses template version rain-daily-periods-v2; below-threshold summaries remain rain-daily-v1. Schema and selection versions are unchanged. Frozen hourly inputs and exact message_text support audit; historical messages are not rewritten.

## Verification

Focused formatter, daily delivery, evidence replay, flood enrichment and intraday tests use mocked LINE clients and disposable SQLite fixtures. PostgreSQL-only cases are skipped when the dedicated test URL is absent. No LINE request, production database write or deployment is performed by this change.

Final test counts and Git verification are recorded below after completion.

Final focused run: 111 passed, 24 skipped, 1 existing python_multipart deprecation warning; exit 0. The 24 skips are PostgreSQL-specific cases; no PostgreSQL sender/locking code changed. New layout/coverage regressions: 17 passed. Mocked daily send, dedupe and frozen evidence replay all passed. git diff --check passed.

Release status: prepared and committed on review/p1-intraday-20261010 only; no production deployment or real LINE send.
