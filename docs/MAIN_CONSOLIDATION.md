# Main consolidation validation - 2026-10-13

The reviewed merge `afbd08e` joins the complete WeatherNow UI/LINE/map baseline (`8045727`) and the older map/release/foundation history. All six original remote branch heads are reachable through this merge. Conflicts were reviewed per file; map imports/components/styles, administrative labels, LINE token handling, audience counters and WeatherNow branding were preserved. Historical release notes and the forecast-integrity checklist were combined.

Validation before creating main:

- Backend non-external suite: 661 passed, 150 skipped, 18 external-integration tests deselected. PostgreSQL-only tests require their dedicated disposable test instance.
- Fixed the imported `pg_sessions` fixture to skip without its explicit PostgreSQL test URL; targeted collection suite: 9 passed, 9 skipped.
- Frontend TypeScript check, optimized Next.js build and lint: passed.
- Existing radar contract QA: 16 cases passed with mocked provider requests.
- Existing radar tile-cache QA: 8 cases passed with mocked network requests.
- The same frontend runtime tree was checked on Production: both audience cards rendered, the LINE login button became enabled, and the map tiles and historical radar loaded for a sample area.

GitHub Actions workflow installation was attempted but the existing OAuth token does not grant the workflow scope. No account permissions were expanded. The test commands are documented in BRANCH_WORKFLOW.md.

Deployment policy: use the tested main revision as the Git source for Vercel Production and Railway app services; verify terminal success and live endpoints before deleting merged remote branches.
