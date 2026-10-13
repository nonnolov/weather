# WeatherNow branch and deployment workflow

- `main` is the canonical, deployable WeatherNow Beta. Keep the Dashboard, LINE onboarding, location/visitor counters, map/radar, and backend in the same tested revision.
- Create `feature/<topic>` or `fix/<topic>` for new work. Merge into `main` after backend tests, frontend typecheck/build, and the affected UI checks pass.
- Before merging, run `python -m pytest -m "not integration"`, `npm ci` and `npm run build` in `frontend`, and the existing radar contract/cache QA scripts. PostgreSQL-specific tests require their explicitly isolated test database.
- GitHub CI was not installed during consolidation because the current OAuth token lacks the `workflow` scope. Vercel still runs the frontend typecheck/build on every Git deployment.
- Vercel Production tracks `main`, with `frontend` as its root directory. Other branches are previews.
- Railway app services track `main`; database service configuration is independent of Git branches.
- Deploy a clean Git revision. Do not combine selected files from different branches or deploy a dirty detached worktree.
- Delete completed feature/release branches only when every commit is reachable from `main` and production has been verified.

## Consolidation on 2026-10-13

The integration starts from `feature/line-onboarding-20261012` at `8045727`, the complete UI/LINE/map baseline verified on Production. It merges `feature/map-radar-20261012` with targeted conflict review. Runtime code remains the verified baseline; the older forecast-integrity checklist and historical deployment records are preserved. The other existing feature, review, release and foundation heads become ancestors through this merge.
