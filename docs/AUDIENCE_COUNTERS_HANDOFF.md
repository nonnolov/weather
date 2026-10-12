# Dashboard audience counters — 2026-10-13 Asia/Bangkok

## Scope and dependencies
Display two small bilingual totals after the brand tagline "เตรียมพร้อมก่อนออกจากบ้าน":
verified LINE accounts and unique website browsers. Requires API migration 0011
after 0010 and the matching frontend release. Production is not updated by this task.

## Counting contract
- LINE: one membership per account after successful server-verified onboarding status.
  Desktop/mobile logins with the same LINE account count once. Notification consent
  is independent; this is not the number of subscribed or currently online users.
- Website: one membership per randomly identified browser profile. A localStorage
  UUID persists across reloads. Clearing browser storage or using another browser/device
  creates another visitor. This is an approximate browser count, not proven unique people.
- Counters start with actual registrations after enabling this release. No historical
  users, webhook identities, forecasts, visits, or fabricated totals are backfilled.
- Private/incognito browsing may count separately. If persistent storage is unavailable,
  use the read-only endpoint and do not generate a fresh identity on every reload.
- Database keys are SHA-256 hashes with kind separation. Metrics store no raw LINE IDs,
  browser UUIDs, IP addresses, coordinates, or tokens. Public endpoints expose only totals.
- Public visitor submission can be automated/spoofed; it is not audited analytics or
  a certified portfolio popularity measurement. LINE totals are never client-supplied.
- Failed/loading requests show a dash, not a misleading zero.

## Implementation and acceptance
Migration 0011 adds a separate audience_members table with a composite primary key;
conflict-safe inserts make retries idempotent. Existing users and notification records
are untouched. GET /api/v1/audience reads totals; POST /api/v1/audience/visit accepts
only a version-4 visitor UUID. Both return Cache-Control: no-store.
Successful LINE onboarding records the server-verified account within the same transaction.
The frontend refreshes totals after connection changes and remains usable if metrics fail.
Small header text wraps for smaller screens and leaves theme/language controls accessible.

## Validation
- 43 backend cases passed: 7 new audience cases plus 36 LINE onboarding regressions.
- Frontend typecheck, lint and production build passed.
- PostgreSQL migration SQL 0010 -> 0011 generated successfully; no production migration
  or real database mutation was run during this task.
- Browser layout/reload checks are recorded in the completion note below.
- No real LINE messages, subscriptions, or fake production visits were generated.

## Release order and rollback
Deploy compatible API and cron source containing migration 0011 before the frontend.
Verify terminal service status, health, public totals, then promote the frontend alias.
Preserve notification flags/schedule and existing production data.
A frontend rollback can hide counters without deleting collected data. For backend rollback
retain a build which recognizes revision 0011; do not deploy an older migration tree or
drop audience data merely to hide this feature.

Browser completion: six mocked scenarios passed at 360/768/1440 px in Light/Dark.
All verify visible counts, stable visitor identity after reload, no horizontal overflow,
no overlap with header controls, and header clearance above main content.
These figures were mocked locally; they are not real production audience statistics.
