# LINE notification onboarding — 2026-10-12

## Scope and baseline
Branch: feature/line-onboarding-20261012. Worktree: weather-line-onboarding-20261012.
Backend baseline: feature/stitch-dashboard-20261012 at 79fca06, the current reviewed backend.
Baseline commit 1b28c25 brings the tested Map frontend from feature/map-radar-20261012 at e540bc0 onto that backend. The Map/release/original dirty worktrees were not modified.
MASTER_ROADMAP.md, DAILY_USE_RELEASE.md and flood-removal handoff remain authoritative for earlier releases.
This implements the user's requested signup flow, not a production rollout or a LINE send authorization.

## Product behavior
Dashboard stays usable without LINE login. Signup is available before a forecast is loaded and remains in the forecast layout.
1. Explicit LINE login button; LIFF sessions already signed in initialize normally.
2. Add/unblock Weather. Full LIFF can requestFriendship; external browsers use the configured LINE friend URL. Return and check status.
3. Explicit GPS permission sets the notification area for the verified LINE identity.
4. Checkbox consent and Enable alerts. Daily summaries and significant intraday updates use the existing policy/timing/deduplication.
Green header light means account authenticated. The separate Alerts enabled badge requires verified friendship, verified current area and persisted consent.
Opt-out has its own API action. A failed disable does not claim success and keeps Retry available.
Unfollow/block disables consent. Follow/unblock does not automatically enable it again. Replayed/out-of-order webhook timestamps cannot undo a later recorded event.
Browsing a sample or panning the Map never reassigns notification location.
HTTP mobile previews can generate a browser identity without crypto.randomUUID. GPS and live LINE still require a suitably configured HTTPS app.

## Backend and security
Migration 0010 adds line_subscriptions with opt-in, friendship, verified location, consent version/time and event timestamp. No token is stored.
Protected endpoints verify the LINE access token's channel ID, expiry, openid/profile scopes and server-returned identity. Request bodies cannot choose another recipient.
- GET /api/v1/line/onboarding/config (public availability/friend URL)
- GET /api/v1/line/onboarding
- PUT /api/v1/line/subscription
- POST /api/v1/line/location/from-gps
- GET /api/v1/line/forecast
- POST /api/v1/line/forecast/refresh
When the feature is on, legacy /users/U... endpoints also require matching verified credentials.
Status and mutation responses use no-store. Access tokens in HTTPX verification URL logs are redacted while preserving logging argument types.
Existing LINE signature verification protects friend webhooks.
User/subscription locks serialize signup, opt-out and the final sender check. A new identity uses a transaction advisory lock to prevent duplicate first registrations.
Daily and intraday recipient discovery uses the same persisted subscription policy. Final locked checks reject disabled/block/missing/inactive/mismatched locations; daily source location is rechecked after locking.
Existing forecast acquisition, alert rules, cooldowns, deduplication and delivery evidence are retained.

## Dependencies and activation
LINE_SUBSCRIPTIONS_ENABLED defaults false: the new signup API is unavailable and legacy sending remains unchanged.
After migration and configuration, true activates both signup and subscription-based recipient selection.
LINE_OFFICIAL_ACCOUNT_ID must be the real Weather account basic/premium ID (for example @...); no account ID was invented.
The LINE Login/LIFF app needs openid and profile scopes, the Weather OA linked to that Login channel, and compatible Messaging API identities under the same provider.
LIFF Full is needed for requestFriendship. The friend-link fallback remains available.
The signature webhook must be registered for the real Weather Messaging API channel and enabled.
The existing LINE channel access token/secret/Login ID and configured daily/intraday jobs must remain correct.
Official references:
https://developers.line.biz/en/reference/line-login/
https://developers.line.biz/en/reference/liff/
https://developers.line.biz/en/docs/line-login/link-a-bot/

## Release risks and acceptance gates
No public recipient expansion, production DB migration, account-console change, real LINE message, push or deployment was performed.
Enabling the subscription feature replaces legacy recipient selection. Existing recipients must explicitly complete the new consent flow; they are not silently opted in.
For a controlled rollout, pause live sends, migrate/configure, enable signup, have the existing account complete enrollment, verify a new account end-to-end, then restore the send schedules after authorization.
Operator must confirm the linked Weather OA and Login/Messaging provider alignment. A wrong/missing link stays unavailable rather than treating login as delivery readiness.
Daily/intraday sends retain provider/platform limits and existing batch caps (10 locations / 100 recipients per scheduler cycle); this is not an unlimited-volume service.
A webhook delay can delay observed block status; LINE itself cannot deliver to a blocked account. Authentication/provider failures do not falsely display readiness.
Production acceptance still requires real Login, friend addition/verification, HTTPS GPS, opt-in/out, block/unblock and explicitly authorized handset receipt.
The localhost QA build uses a dummy public LIFF ID with SDK/API/browser requests mocked. It proves UI behavior, not live LINE enrollment.

## Verification
Build includes TypeScript, Next compilation and lint.
New API/security/consent unit suite; PostgreSQL race/eligibility/migration tests on a dedicated localhost PostgreSQL 16 test instance and random schemas.
Browser suite covers Light/Dark mobile/Desktop, explicit login, friend addition, external-browser fallback, GPS, consent, opt-out/retry, token expiry, friendship/enable/disable failures and block state.
All automated LINE SDK/API/send operations are mocked. There are no production writes or real messages.
See LINE_ONBOARDING_QA.json for final counts/status and outstanding real-service gates.
Local preview is http://localhost:3103 on the Remote PC. Existing Map preview remains at 3102.

## Final ordering/configuration checks
Signup is advertised as available only when Login channel, Messaging token/secret and Weather account ID are configured. Enabling the flag with missing settings fails validation rather than showing a false delivery-ready state.
Friendship event ordering and consent ordering are independent: a block/follow event revokes an older grant even if delivered out of order, while an explicit grant newer than the event is retained. Neither follow nor status polling grants consent.
Client status requests carry a revision guard. Visibility refresh is suspended during subscription mutations, and older responses cannot replace an opt-out result. A failed opt-out remains retryable without pretending it succeeded.
Final focused backend verification covers 68 cases, including 32 signup/security cases and 9 PostgreSQL race/migration/adapter cases.

Final browser signup suite passed 13 scenarios; existing Dashboard (10), GPS/data flows (12) and Map (10) also passed against the new frontend. Final frontend build passed TypeScript/compilation/lint.
The broader backend run passed 777 cases with 10 environment-dependent skips before the final signup guards; the affected backend paths were subsequently rechecked with the 68-case focused suite.
Rollback should disable the signup feature and restore the compatible sender/frontend release while retaining the subscription table and consent evidence.
