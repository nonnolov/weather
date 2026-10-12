# Map and past radar — 2026-10-12

Branch: feature/map-radar-20261012. Isolated worktree: weather-map-20261012.
Started from release/dashboard-20261012 at 4f44e7b. Original feature/frontend-ux and its uncommitted changes were left untouched.
Read MASTER_ROADMAP.md, DAILY_USE_RELEASE.md and REMOVE_FLOOD_UI_LINE_HANDOFF.md in the existing review/worktrees before implementation.
Scope requested: Map features; no GPS accuracy addition.

## Behavior
- Existing Map button opens a full-screen Leaflet 1.9.4 map using the displayed forecast area's coordinates. Sample areas are explicitly labelled.
- Pan, zoom and Centre on area operate locally; opening/closing Map does not request GPS or write the user's location.
- OpenStreetMap base tiles and visible attribution.
- RainViewer past radar: toggle layer, keyboard-accessible time slider, Play/Pause, frame time with area timezone, and reload.
- No future nowcast, flood score, flood UI or flood text in LINE.
- Optional coverage mask and point coverage check. Blank radar areas do not imply no rain. Coverage is a provider mask, not guaranteed live station status.
- Invalid coordinates are explained rather than replaced with an arbitrary location.
- Metadata/tile failure leaves the base map available; stale frames are labelled and playback disabled.
- Modal Escape/back restores Dashboard and body scrolling. Layers, images, timers and observers are cancelled on close.

## Data and limits
Metadata: https://api.rainviewer.com/public/weather-maps.json
Official docs:
https://www.rainviewer.com/api/weather-maps-api.html
https://www.rainviewer.com/api/transition-faq.html
https://www.rainviewer.com/api/color-schemes.html
https://operations.osmfoundation.org/policies/tiles/

Follow detailed/transition docs and actual API: past frames only, max native radar zoom 7, Universal Blue color 2. Radar tiles are enlarged above zoom 7; additional detail is not claimed.
Client queues at most 80 RainViewer image starts per minute per page (including coverage), visible tiles only, no prefetch. Playback slows for wide viewports and waits for layer loading. This cannot guarantee an IP-wide quota when several users/tabs share an IP.
Metadata endpoint has fixed upstream/host validation, bounded frame count/path/time, 8-second timeout, deduplication, 5-minute memory cache, 30-second retry cooldown, and at most 30-minute last-good fallback marked stale.
CDN cache provides additional caching; memory cache is per server instance. Small personal/community use follows RainViewer's free API scope; revisit provider/service terms before a public commercial/high-volume rollout.
Attribution: OpenStreetMap contributors and Weather data by RainViewer remain visible.

## Preview and release
Remote PC preview: http://localhost:3102 (LAN http://192.168.1.7:3102).
Production remains the deployed mobile LINE Dashboard at source 7508ea2. Map has not been pushed, promoted or deployed.
Backend, database, schedules, LIFF configuration, LINE recipient, GPS accuracy and Light/Dark palette are unchanged.
Preview does not contain production LIFF configuration; live LINE authentication must be verified on a configured deployment.

## Validation
npm run build includes explicit TypeScript check, compilation and lint.
radar_contract_qa.cjs: 16 validation/cache/failure/recovery cases, upstream mocked.
stitch_dashboard_qa.cjs: 10 viewport/theme cases, Map open/close, 24 hourly/7 daily, LINE indicator, charts and artwork.
stitch_dashboard_flows_qa.cjs: 12 GPS/forecast/air-quality flows, backend mocked.
map_qa.cjs: mobile/desktop interaction, playback/slider/toggles/pan/zoom/centre/reload/close, metadata error/empty/stale, base/radar tile errors, coverage unknown/uncovered, invalid coordinates.
Automated browser tests stub all OSM/RainViewer tile requests; screenshots show synthetic tiles and must not be described as real rain observations.
One manual feasibility request used fixed public Bangkok coordinates; real provider metadata and PNG tiles returned successfully. No private user location was retrieved for provider tests.

Accessibility/cleanup: keyboard focus returns to the invoking Map button, and viewport screenshots were reviewed at 360 and 1440 pixels. Leaflet zoom tween is disabled to avoid delayed zoom callbacks after modal unmount; panning and zoom controls remain functional.
