# Stitch dashboard adaptation — 2026-10-12 Bangkok

Source: user-uploaded stitch_minimalist_thai_weather_dashboard.zip, with desktop/mobile Dashboard and Map designs and Quiet Atmosphere tokens.

Branch: feature/stitch-dashboard-20261012, based on 06f7a95. The other worktree weather / feature/frontend-ux and its pending files are untouched.

## Behavior
Forest-green/off-white responsive Dashboard, 24-hour scrolling forecast including rainfall units, switchable temperature/rain charts, existing model PM2.5 card and connection state. GPS/API/LIFF logic remains in the existing page.
View map opens a full-screen accessible native dialog, preserving Dashboard state and scroll; Escape/back closes it. It displays an explicit unavailable state, without fake map/radar data. No map API, GPS write or LINE send is introduced.
No Stitch sample station names, accuracy, uptime, latency or notification thresholds are included.
Chart SVG circles use cx/cy so markers follow the actual data points.

## Validation
ESLint, explicit TypeScript noEmit and production build passed before final marker/font refinement; rerun required below.
Browser QA at 390 and 1440 passed: 24 hours/7 days, chart switching, Map open/Escape return, no page overflow/errors, no map-triggered requests, no writes or flood requests. Browser responses were mocked; this does not verify handset GPS or LINE login.
Run node scripts/stitch_dashboard_qa.cjs against a local production server on port 3100. It uses installed Chrome and the npm-exec Playwright cache; screenshots are local temporary QA outputs, not tracked source.
Final checks and commit are recorded in the session.

## Release boundary
Not deployed. Leaflet/radar remain unimplemented. Real handset/LIFF visual acceptance remains open. Existing production stays at the flood-removal release.

Final lint, explicit tsc --noEmit and production build all exit 0 after marker/font refinement. A local preview server is started on port 3100 for review; not a production deployment.

Logo follow-up: replace the green W badge with the existing SVG WeatherArtwork, driven by the displayed forecast hour's weather_code. A cloudy icon is shown before data is loaded; descriptive Thai/English accessible text is included. No new image service, dependency or API calls. The forecast art supports clear, cloudy, rain, thunderstorm, snow and fog conditions.

## Fidelity correction after user review
The user requested closer adherence to the supplied Stitch export, including UI motion. The second archive contains the same desktop HTML/screenshot plus DESIGN.md. The original mobile/map export remains the mobile reference.
Added the fixed blurred header, compact navigation, location/update label inside the weather hero, feels-like from API data, four desktop metric blocks, probability progress bar, compact expandable seven-day rows, smaller PM2.5 details, and IBM Plex Sans/Thai with system fallbacks.
Motion follows exported interactions: 150ms pressed button scale, 200ms hour-card lift/hover, rotating GPS icon, real connected-LINE status ping, 300ms chart entry, expandable detail transitions. Reduced-motion disables animation/transitions. Charts now expose a keyboard/touch hour selector and tooltip populated from actual forecast values, instead of the export's hard-coded sample tooltip.
User-selected weather logo and black/charcoal dark theme remain.
Unsupported station names, model accuracy/latency numbers, fake recipients/thresholds, and developer simulation controls are excluded. These are deliberate data/product corrections, not a claim of pixel-identical reproduction.
Final production build/typecheck/lint completed with exit 0 and no CSS warnings. Browser validation is recorded in the session.

Desktop readability follow-up: at widths >= 1024px, supporting text is 14px, section headings 21px, location title 24px and hero temperature 88px. Mobile sizes are preserved. Air-quality heading can wrap to avoid colliding with the refresh button.

## Dashboard component rebuild — 2026-10-12

Rebuilt the presentation layer around the supplied Stitch desktop/mobile export, with the requested black dark canvas, charcoal cards, weather-dependent cloud branding and larger desktop text.

- `app/page.tsx` now mounts the LIFF script and DashboardView.
- `app/dashboard/useWeatherDashboard.ts` owns the existing GPS, seed-area, API, browser identity, language/theme and LIFF flows; backend API contracts are unchanged.
- Header, current conditions, hourly outlook, daily outlook and charts are separate components. Formatting and outline SVG icons are shared.
- `globals.css` contains shared tokens/primitives, `dashboard/dashboard.css` owns layout and interaction styles, and the air-quality component keeps a scoped CSS module. Superseded stitch.css/fidelity.css were removed instead of retaining override chains.
- IBM Plex Sans / IBM Plex Sans Thai are self-hosted in public/fonts, including SIL Open Font License notices. No runtime Google Fonts/CDN dependency.
- Forecast charts support pointer inspection and a keyboard-accessible hour scrubber. Hover/press/fade/ping interactions respect reduced motion.
- Daily rain probability prefers the daily API field, falling back to hourly-derived probability when the daily field is missing.
- PM2.5 category badges use the API's European AQI category. No fabricated station readings, Thai AQI thresholds, accuracy percentages, uptime, alert settings or model metadata were copied from the design sample.
- Map remains a full-screen unavailable state; Leaflet/radar are still pending. No flood card or flood API calls were added.
- QA uses mocked responses only: Thai/English layouts, six viewport/theme combinations (390/1024/1440/1920px), modal/API isolation, chart controls, reduced motion, missing/stale/failed PM data, empty/failed forecast, GPS denied and GPS success. The GPS success test intercepts both POSTs; no production writes.
- Preview on the connected PC: http://localhost:3100. This change is not pushed or deployed.
