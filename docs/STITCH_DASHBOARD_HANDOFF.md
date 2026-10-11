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
