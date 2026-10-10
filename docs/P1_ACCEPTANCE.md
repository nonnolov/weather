# P1 acceptance and operations record

Current integration: P1-12, deployed SUCCESS and live intraday enabled under
explicit user authorization on 2026-10-10 at 18:31:37 Bangkok. One existing
recipient is allowlisted. Local tests use mocks; the native production live cycle
has been observed suppressing identical content. A positive real intraday send
has not occurred. This review package contains the deployed P1-12 runtime and
its tests/rollout record. Exact commit and remote verification are reported
with the separately authorized GitHub upload.

## Implemented and checked

| Requirement | Evidence |
| --- | --- |
| Aligned future hours, significance, freshness and cooldown | P1-02 deterministic comparator tests |
| Latest committed frozen accepted baseline, no unknown fallback | P1-03 owned-history adapter |
| Shared daily/intraday scope and row locks | P1-04 real PostgreSQL concurrency tests |
| Trigger-bearing text, frozen evidence, acceptance failure handling | P1-05 mocked sender and commit tests |
| Latest committed candidate and final recheck | P1-06 preview reader/CLI |
| Existing source cadence and platform/provider audit | P1-07 read-only production audit |
| Source commit before explicit-refresh preview | P1-08 default-off request bridge |
| Fresh actual daily accepted evidence -> P1 preview | P1-09 separately authorized controlled production check |
| Existing API lifespan, forecast-only periodic preview | P1-10 default-off owned scheduler |
| Duplicate worker and bounded scope prevention | Nonblocking PostgreSQL cycle lock; 10 locations/100 recipients |
| Error/cancellation isolation | Deadlines, source rollback before commit; committed sources retained afterward |
| Normal daily job preserved | Daily CLI and 06:00 Bangkok cron unchanged |
| Default-off live scheduler and explicit recipient allowlist | P1-12 local live adapter tests |
| Durable halt across ambiguous send/commit and process restart | P1-12 intent migration and real PostgreSQL mocked tests |

P1-08 and P1-10 flags are independently false by default. Preview has no real
LINE sender or accepted-delivery write. The periodic path calls only forecast
ingestion, never rolling observation ingestion or the daily LINE CLI.

## P1-12 local validation

439 passed, 18 live integration cases deselected, one existing python_multipart
warning, 273.20 seconds, exit 0. No selected cases skipped. The 19 new cases cover
allowlisting/configuration, native scheduler routing, durable intent before push,
replay/concurrency, timeout/cancellation/rejection, new-source blocking, failed
intent commit, acceptance/commit failure and additive migration with seeded
frozen history preservation. No live provider/LINE or production DB write.

See P1_12_LIVE_DELIVERY_HANDOFF.md for rollout and unresolved-send handling.
P1-12 implementation, local validation and authorized production activation
are complete. Positive send acceptance and later scheduled observations remain
separate evidence gates for closing P1.

## P1-11 local validation (historical)

420 passed, 18 live integration tests deselected, one existing Starlette
python_multipart warning, 231.11 seconds, exit 0. No selected cases skipped.
This includes 20 new scheduler cases, 15 post-commit cases, P1 PostgreSQL
serialization and four P0 migration/evidence PostgreSQL cases.

Targeted bridge/scheduler run: 35 passed, one existing warning, 45.61 seconds,
exit 0. Tests used a dedicated temporary PostgreSQL 16 cluster at localhost
55434 and disposable random schemas. dotenv reads and LINE credentials were
disabled, proxy variables removed, and external socket connections blocked.
No real provider, LINE or production database write occurred in these local
runs. The dedicated test cluster was stopped and removed after completion.

## Controlled production acceptance

On October 10, under separate user authorization, one fresh forecast was
committed (source 40), one daily LINE API push was accepted, and one delivery
was committed (delivery 5). Frozen schema-v1 evidence retains 24 hourly
intervals, exact message and source identity. P1 preview read that baseline and
suppressed identical_content. An independent read-only recheck confirmed
today's daily key and the same preview outcome.

See P1_09_CONTROLLED_ACCEPTANCE.md and sanitized JSON. This resolves the
immediate no-baseline/stale-source gate from the earlier audit. It establishes
API acceptance and DB durability, not independently verified handset receipt.
Date-scoped daily dedupe does not automatically suppress tomorrow's daily key.

## P1-12 production rollout

Deployment bf7c1724-7445-4395-a40d-81056f8b80a9 reached SUCCESS. The package uses
baseline 39e4471 plus eight reviewed runtime overlays, without a new Git commit.
All 68 deployed app/Alembic Python hashes match. Migration 0007 and both unique
intent indexes are confirmed; original frozen baseline retained. Fresh private
custom backup/archive listing is recorded in P1_12_LIVE_DELIVERY_HANDOFF.md.

Live/scheduler flags are true, messaging credential references the existing
cron token, and the allowlist is exactly one previously accepted recipient.
Internal/public health HTTP 200. Native live tick at 18:43:22 Bangkok:
complete, fresh=1, refreshed=0, processed=1, suppress/identical_content=1.
Counts remain five total deliveries, zero intraday deliveries and zero intents.
No artificial change, manual cycle or forced message was used to manufacture
a positive result. Daily cron remains unchanged.

The next tick is estimated around 18:58:22 Bangkok plus processing time. Later
hourly due-source refresh, positive significant-change acceptance and the normal
daily scheduled evidence remain unobserved gates. Rollback keeps schema/code
0007 and disables the live flag; direct P1-11 rollback with its old predeploy
cannot resolve revision 0007. Do not drop intent records.

## P1-11 production boundary (historical)

- API deployment 515a5c49-b042-4833-bd30-23ba3fef97ba reached SUCCESS with
  source commit 6eda58f. All 57 deployed app Python hashes match the archive.
  Both preview flags are true in production and no messaging token is present.
- The real request post-commit hook and first native timed cycle both processed
  one recipient and suppressed identical_content. The native tick completed at
  17:48:20 Bangkok, reusing fresh source 41. Delivery counts stayed five total,
  zero intraday. See P1_11_PRODUCTION_PREVIEW_HANDOFF.md and sanitized JSON.
  Later due-source refresh and continuous uptime/cadence remain observational
  checks; a single timed cycle is not proof of all future ticks.
- The existing normal daily cron has not yet been observed accepting a
  source-linked frozen delivery after its evidence release; October 10's
  controlled process is distinct from that scheduled path.
- Capacity estimates and fresh usage/storage reads are recorded in
  P1_10_SCHEDULED_PREVIEW_HANDOFF.md and P1_10_CAPACITY.json. No new service,
  paid dependency or upgrade was introduced. Future billed usage and shared
  provider quota headroom are not guaranteed.
- Production preview rollout is complete at the request/native-startup-tick
  boundary. Continue observing fresh sources, aggregate logs and usage.
  Both flags false and redeployment disable preview work.
- P1-12 locally wires the existing locked sender into the scheduler behind a
  separate default-off live flag and explicit recipient allowlist. Migration
  0007 retains unresolved send intent across crashes. See
  P1_12_LIVE_DELIVERY_HANDOFF.md for failure handling and rollout preparation.
  At that historical boundary, deployed P1-11 had no live path or messaging credentials.

P1-11 established preview activation. P1-12 above supersedes that deployment
with an explicitly enabled live path. Neither the original preview tick nor the
first suppressed live tick proves positive LINE acceptance or continuous uptime.
Longer-term cadence and the normal daily cron acceptance remain separate checks.

## Failure handling for a future live sender

| Outcome | Meaning and response |
| --- | --- |
| preview/skip/suppress | No LINE call or baseline advance |
| sent with delivery ID | API accepted and helper committed; handset receipt unknown |
| explicit LINE rejection | No accepted record; diagnose before operator-authorized retry |
| SendOutcomeUnknown/cancellation during push | Stop automatic retry and reconcile accepted event identity |
| AcceptedDeliveryNotCommitted | Do not claim durable success or blindly retry |

Inspect committed event identity in an owned read-only session for an ambiguous
send. Absence does not prove rejection. Do not reconstruct old evidence from
new source rows, reset cooldown or fabricate acceptance. Network acceptance
and DB commit cannot be made atomic by these helpers.

Preview errors require no send reconciliation because preview never calls LINE.
Lost/truncated previews are best effort and must not be reported as complete
recipient coverage. Retrieval timestamps do not establish provider model age.

## GitHub and preservation

GitHub CLI verifies private nonnolov/weather and sets its credential helper;
git performs the local commit and ordinary push to
review/p1-intraday-20261010. No default-branch update, force push, merge, PR or
deployment is included. Remote SHA must match the local integration SHA.

Original 34 dirty files retain their checkpoint hashes; original
feature/frontend-ux branch, fc3d29c5203916a26e3c6c0a33f3712cc263da2e HEAD and
empty index are preserved. The unrelated original frontend release note is
excluded. See P1_GITHUB_HANDOFF.md for package and deployment-trigger evidence.


## P1-14 production follow-up

The authorized P1-14 code is committed and pushed, and the existing API now runs `intraday-v2-candidate` on successful deployment `08eda3b9-d345-40d3-8f75-cff4ff0b5eb3`. See `P1_14_POLICY_DELIVERY_HANDOFF.md` and `P1_14_PRODUCTION_RELEASE.json` for source, health, cadence and preservation verification. Earlier offline-only and P1-12/v1 statements describe the earlier stages. Positive real intraday LINE acceptance and handset receipt remain open; no qualifying event was fabricated to close them.
