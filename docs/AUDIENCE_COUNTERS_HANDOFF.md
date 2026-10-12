# Dashboard location and visitor cards — 2026-10-13 Asia/Bangkok

## Scope and dependencies
Two bilingual rounded cards follow the brand tagline: locations received from users,
and unique website browsers. On desktop they sit beside the brand; below 1200 px they
occupy a separate two-card header row. Requires migration 0011 after 0010 and the matching
frontend. This task updates local preview only; production is not deployed.

## Counting contract
- Locations: unique saved GPS-location records received successfully through browser or
  authenticated LINE GPS endpoints. The same saved location counts once across users
  and retries; moving to a different stored location adds a record. Prior counted locations
  remain counted when the user's current area changes.
- Sample/seed locations and merely logging in with LINE do not add locations.
  Failed geocoding does not count. GPS coordinate variations can create separate location
  records; the total is not a count of unique districts, users or GPS button clicks.
- Website: unique random browser-profile UUID persisted in localStorage. Reload does
  not increase the same browser's total. Another browser/device, incognito or cleared
  storage may count separately; these are approximate browsers, not verified unique people.
- Counters begin with real registrations when the feature is enabled. No historical
  counts or artificial numbers are backfilled. Storage-unavailable visitors use GET only.
- Membership keys are SHA-256 hashes with kind separation. Metrics store no raw browser
  IDs, user IDs, coordinates, IP addresses or credentials. Public responses expose totals only.
- Public visit input may be automated/spoofed, so this is not certified popularity analytics.
  Clients cannot directly submit a location total through the metrics endpoint.
- Unavailable/loading totals show a dash rather than a fabricated zero.

## Implementation
Migration 0011 adds audience_members with browser/location kinds and a composite primary
key. Conflict-safe inserts make retries idempotent. Successful GPS saving records the
location within the same transaction as the user's location update. Visitor counting is
independent of LINE login/notification consent. GET /api/v1/audience and POST
/api/v1/audience/visit return received_locations and website_visitors, no-store.
Frontend totals reload when the displayed location changes.

## Migration status
The earlier LINE-login counter version of 0011 was never deployed. Its pending schema
is revised to browser/location with a String(8) kind, not applied over a deployed 0011.
The disposable earlier local-preview database is retained separately; this version uses
a new isolated local database. No production migration or historical data rewrite occurs.

## Validation
50 backend cases passed: 9 audience, 5 user-location and 36 LINE-onboarding cases.
Frontend typecheck, lint and production build passed. Browser card/layout checks will
be recorded below after completion. Real LINE messages/subscriptions were not generated.

## Release and rollback
Deploy compatible API and daily-cron source containing 0011 before promoting the frontend.
Preserve notification flags, consent and cron schedule. Verify terminal status, health and
public totals. A frontend rollback may hide cards while retaining data. A backend rollback
must still recognize revision 0011; do not drop audience records to hide the cards.

Browser completion: all six mocked card scenarios passed at 360/768/1440 px in
Light/Dark, with visible totals, reload deduplication, no horizontal overflow,
no overlap with header controls and sufficient main-content clearance. Desktop Light
and mobile Dark screenshots were visually inspected. These mock totals are not real
production audience counts. Local preview uses its separate SQLite database at port 3111.

## Production release (supersedes local-only status above)
User authorized deployment on 2026-10-13. API and daily cron reached SUCCESS; migration
0010 -> 0011 completed, and the frontend reached READY with its stable alias promoted.
Real public browser checks at 1440/360 px show both rounded cards without page errors.
One real smoke-test browser registered once across reloads; this is included in the
observed visitor total, not a claim of an external human audience. Location total was zero
because historical GPS rows and scheduled refreshes are not backfilled/count events.
Health and LINE config returned 200; signup remains enabled and anonymous protected
onboarding returns 401. Intraday live cycle completed, refreshed one location and skipped
no_baseline with no refresh failure. No manual LINE message or production GPS update was
performed. See AUDIENCE_COUNTERS_RELEASE.json for deployment IDs and evidence.
