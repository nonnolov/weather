# Dashboard release preparation — 2026-10-12 Bangkok

## Candidate
- Release branch: release/dashboard-20261012, based on origin/phase-1-backend-foundation at d446eac.
- Dashboard source: feature/stitch-dashboard-20261012 at 79fca06.
- Only frontend files, Dashboard QA scripts and release documentation are included. The older dirty weather / feature/frontend-ux worktree and the original Dashboard worktree were not overwritten.
- GitHub's default branch is behind the already deployed backend implementation. Do not merge the whole Dashboard development branch or trigger a backend deployment as part of this frontend release.
- Backend, schema, schedulers, recipients, alert policy and existing flood-removal behavior are unchanged.

## Included behavior
Stitch Dashboard, black/charcoal dark theme, local Thai fonts, realistic weather artwork, larger main weather image, complete province/subdistrict/district header, visible LINE connection glow, accessible charts and GPS error/saved-data recovery.
The Map button remains visible by user choice; it opens the explicit unavailable dialog. Leaflet/radar are not implemented.
Weather remains model forecast data; air quality remains model PM2.5/European AQI.

## Dependency preparation
Next.js and eslint-config-next are pinned to 15.5.27. PostCSS is overridden to 8.5.29 within major 8, and the lockfile resolves Sharp 0.35.5 within Next's supported range.
Production dependency audit reports 0 vulnerabilities. Full audit retains 5 high findings in the development-only ESLint glob/braces chain; braces 3.0.3 is currently the registry's latest stable release. These tools scan repository patterns during development/build, not public request patterns. Do not use audit fix --force to downgrade/switch framework or lint majors.

## Verified on the release worktree
- Clean lockfile installation; explicit lint, TypeScript noEmit and production build exit 0.
- 8 viewport/theme combinations (390,1024,1280,1366,1440,1920): no page overflow/errors, complete province, visible desktop LINE light, all 7 weather assets, 24 hours/7 days, chart controls, Thai/English, Map Escape and no Map API calls, reduced motion.
- 12 mocked flows: air missing/stale/failure; forecast empty/failure; GPS permission denial/success/location failure/refresh failure; valid saved data/wrong area/expired saved data.
- QA intercepts all backend requests; no production GPS POST, forecast refresh or LINE sends.
- Vercel dry-run identifies Next.js and excludes private env files, git and dependency artifacts.
- Existing production root and /api/backend/health return HTTP 200.
- Existing Vercel project weather, ID prj_K6LybtzdJhZhL4ajYrD0755JRJGV, scope weather-9c1f, Root Directory frontend, configured Node 24.x.
- Existing API_BASE_URL, NEXT_PUBLIC_API_BASE_URL and NEXT_PUBLIC_LIFF_ID are configured for Production only. Values were not copied to committed files. Preview environments do not establish real LIFF readiness.

## Production release completed
Preparation was followed by the user-authorized production release. Deployment dpl_HbSvuo9pf7GcdBcZ5Bu3gQ4zQmwF is READY and the existing stable alias has been switched and verified. See DASHBOARD_PRODUCTION_RELEASE.json. The commands below remain the reusable release/rollback procedure.
After authorization, deploy this release directory to the existing project with Production configuration but keep domains unchanged:
```powershell
vercel deploy --project prj_K6LybtzdJhZhL4ajYrD0755JRJGV --scope weather-9c1f --prod --skip-domain --yes
```
Run from the release repo root, not frontend (the project already has Root Directory frontend).
Wait for terminal READY; inspect that exact candidate and verify its root/proxy health, optimized images and Dashboard behavior. Then promote the candidate and explicitly verify the legacy stable alias weather-iota-five-83.vercel.app points to it. If the legacy alias does not move automatically, assign only that alias explicitly.

Current production rollback target: dpl_G5wmjDJjXMkkmYdXw6mbpquaK56L / https://weather-g2i5ysabl-weather-9c1f.vercel.app. Both weather-iota-five-83.vercel.app and weather-weather-9c1f.vercel.app currently point to it.
On a failed release, restore the previous deployment and these existing aliases, then verify root/proxy health. Do not change Railway services, migrations or delivery evidence for a frontend rollback.

## Remaining real-device acceptance
After promotion, the user opens the existing LINE/LIFF entry on a handset, confirms the correct province/subdistrict/district, grants location permission, updates GPS and checks fresh forecast/model air data and real connected-LINE glow. The operator will not reuse coordinates or user identity from logs without authorization.
Natural positive intraday receipt remains a separate historical acceptance gate. No forced weather event or message is introduced.
