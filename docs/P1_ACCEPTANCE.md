# P1 acceptance and operations record

Current prepared integration: P1-10, periodic forecast-only preview in the
existing API. This document separates checked implementation from active
production behavior. The user authorized ordered preparation, capacity review,
testing and GitHub commit/push after those checks. Deployment and real intraday
LINE activation remain separate.

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

P1-08 and P1-10 flags are independently false by default. Preview has no real
LINE sender or accepted-delivery write. The periodic path calls only forecast
ingestion, never rolling observation ingestion or the daily LINE CLI.

## Final local validation

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

## Production boundary

- No automatic P1 task has been deployed or activated. Local repeated ticks,
  actual lifespan tests and the production one-off do not prove continuous
  deployed cadence.
- The existing normal daily cron has not yet been observed accepting a
  source-linked frozen delivery after its evidence release; October 10's
  controlled process is distinct from that scheduled path.
- Capacity estimates and fresh usage/storage reads are recorded in
  P1_10_SCHEDULED_PREVIEW_HANDOFF.md and P1_10_CAPACITY.json. No new service,
  paid dependency or upgrade was introduced. Future billed usage and shared
  provider quota headroom are not guaranteed.
- A future authorized rollout must deploy the reviewed API commit, enable
  preview flags, observe real ticks/fresh sources and check aggregate logs.
  Both flags false and redeployment disable preview work.
- Real intraday LINE activation requires reviewed recipient authorization,
  explicit enablement and operator handling. No real intraday sender is wired
  into API or scheduler, and API does not receive messaging credentials.

Automatic preview preparation is complete and testable. P1 is not described
as production-complete or continuously sending LINE while those operations
remain unverified.

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
