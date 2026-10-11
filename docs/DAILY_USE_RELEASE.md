# Daily-use release — 2026-10-11 Asia/Bangkok

## Authorized minimum scope
The user selected the fastest route to a usable everyday project, retained Open-Meteo, and deferred forecast-accuracy research. This is a controlled daily-use release for the existing LINE recipient, not a declaration that every original P0–P7 acceptance gate has passed.

## Ready to use
- Open the production dashboard: https://weather-iota-five-83.vercel.app/
- For LINE-linked GPS/alerts, open through the existing LINE/LIFF entry, wait for connection, allow location access and press the location button. When moving to another area, update the location again; the application does not track background movement.
- The dashboard combines local hourly/7-day weather, rain probability and amount, temperature/rain charts, model PM2.5.
- The existing daily job is configured for 06:00 Bangkok. Both rain alerts and below-threshold summaries use the existing daily workflow and duplicate protection.
- Intraday polling is enabled with 15-minute delays after completed cycles and hourly due-forecast refresh. Sending remains restricted to the existing allowlisted LINE recipient, significant-change policy and duplicate/cooldown rules. A qualifying update can therefore be suppressed; there is no promise of a message every tick.
- Browser-only identities can load GPS forecasts but are excluded from LINE scheduled refresh/sending. Their stored forecasts may grow old; request GPS/refresh again to retrieve current weather. Sample seed forecasts are historical examples, not an alternative to current GPS retrieval.
- Shared nearby GPS acquisition preserves user location records and immutable alert evidence. Google preview remains off.

## Production checks
See DAILY_USE_ACCEPTANCE.json for the time-specific HTTP and read-only DB evidence.
- Frontend and backend proxy health HTTP 200.
- Existing LINE location 15: Open-Meteo forecast, seven daily records, at least 24 continuous future hours, present/valid essential hourly temperature/rain/probability.
- PM2.5 available, explicitly model estimates rather than measured station readings.
- Rainfall data available; Chon Buri flood assessment remains not_assessed, never interpreted as low risk.
- Native scheduler complete at 19:02, 19:17 and 19:32 Bangkok; final cycle refreshed successfully, refresh_failed=0, suppressed identical_content, no truncated scope.
- Read-only runtime flags confirm scheduler/live enabled, one recipient allowlisted and no unresolved send intents.
- Frontend TypeScript noEmit and ESLint: exit 0. Prior runtime regression: 751 passed, 6 skipped with the existing warning; see FORECAST_FETCH_CONTROL_RELEASE.json. No runtime source changed in this closure step.
- Daily LINE was accepted earlier today and handset receipt confirmed by the user. No additional real LINE test, user reassignment or forced weather event was performed for this closure.
- Public HTTP checks do not replace a fresh handset GPS/LIFF permission check on every browser/device.

## Master phase disposition
| Phase | Daily-use disposition | Original gate retained |
| --- | --- | --- |
| P0 | Existing production baseline retained | Long-term uptime not guaranteed by a smoke check |
| P1 | Daily/intraday features enabled for existing recipient | Natural positive intraday send/receipt remains unobserved |
| P2 | Collection/report code retained; numerical validation deferred | Eligible measured baseline and verified station interval contract |
| P3 | Model PM2.5 shown in dashboard | No claim of a local station measurement |
| P4 | Withdrawn from dashboard and LINE by user on 2026-10-11 21:18 Bangkok | Historical code/data retained; no active flood assessment feature |
| P5 | Optional real flood integration deferred | No confirmed flood detection claimed |
| P6 | Existing combined dashboard satisfies minimum presentation scope | No new dashboard redesign or new-device visual acceptance in this step |
| P7 | Time-specific production smoke and scoped release record completed | Original end-to-end natural-event and device gates remain open |

Dependencies are the existing Vercel frontend, Railway API/PostgreSQL/daily cron, Open-Meteo, location permission, LINE login/friendship and the existing allowlist. Forecasts guide daily preparation; they do not establish actual rain/flood occurrence. Model PM2.5, missing data and unsupported flood assessment retain their labels.

## Reusable operator check
Run from the repository:
```powershell
python scripts/daily_use_smoke.py --base-url https://weather-iota-five-83.vercel.app/api/backend --location-id 15
```
Use the current location ID when it changes. The checker uses only GET endpoints, never GPS writes, forecast refresh POST or LINE sends. Air-quality GET can refresh its bounded model cache. A stale/partial optional air-quality result is a warning; stale or incomplete essential forecasts fail. It reports status without recipient IDs, exact coordinates or credentials.

If the check fails, inspect API health, current GPS forecast freshness and native scheduler logs before changing provider or retrying a message. Never clear send-intent or delivery evidence to fix an alert. Location 15 is a checked snapshot, not a permanent hard-coded recipient assignment.

## Freeze and follow-up
No new API/provider, infrastructure, paid plan, scheduled message or recipient expansion is added. The existing deployed code remains the runtime baseline; this change adds an operator check and documentation only, so no redeploy is needed. Use the current system and repair demonstrated daily-use defects. P2/P5 research and natural-event observation can continue later without blocking this scoped release or fabricating completion.

## Scope update — 2026-10-11 21:18 Bangkok

The user removed the accumulated-rain/flood-risk card and flood-watch paragraphs from new daily/intraday LINE alerts. Earlier production checks above and DAILY_USE_ACCEPTANCE.json are historical evidence, not an active flood feature. See REMOVE_FLOOD_UI_LINE_HANDOFF.md and REMOVE_FLOOD_UI_LINE_RELEASE.json for this release. Normal rainfall quantities and forecast charts remain. The operator smoke check no longer requests the retired flood card endpoint.
