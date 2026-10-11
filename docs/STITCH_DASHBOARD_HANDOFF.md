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
