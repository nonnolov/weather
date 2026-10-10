# P1-14: explicit policy integration and delivery verification

Scope: connect the P1-13 candidate rules to the locked delivery path, preview and live adapters; verify without sending LINE. Initial validation was performed in the review worktree. The authorized production release is recorded below.

## Rules

| Rule | Production v1 | Selectable v2 candidate |
| --- | --- | --- |
| Qualifying forecast hour | Probability >=70% OR hourly rainfall >=10 mm | Same thresholds |
| Increase | >=20 percentage points OR >=5 mm in a qualifying hour | Same; crossing either threshold also qualifies even below these deltas |
| Earlier onset | >=2 hours earlier, onset <=4 hours away | Same; additionally >=1 hour earlier if onset <=2 hours away |
| Normal cooldown | 3 hours from latest accepted rain delivery, including daily | Same |
| Cooldown exception | None | Trigger hour starts <=2 hours away AND threshold crossing, qualifying earlier onset, or >=5 mm rainfall increase |
| Probability-only increase when already qualifying | Subject to cooldown | Subject to cooldown; does not bypass it |
| Identical content / invalid evidence | Suppress / skip | Same |

Cooldown is evaluated every tick. A suppressed event is not a guaranteed queued message: the next tick rechecks fresh evidence and the latest accepted baseline. Once 3 hours have elapsed, it sends only if it still qualifies. Failed or ambiguous sends do not establish a new accepted baseline; a pending durable intent blocks automatic retry until resolved.

The candidate two-hour exception is an operational rule, not proof of meteorological accuracy. Original scope, source freshness/order, day/window coverage and evidence checks remain in force.

## Integration

`INTRADAY_POLICY_VERSION` explicitly selects `intraday-v1` (default) or `intraday-v2-candidate`. Preview and live adapters pass the same selection through locked evaluation, final pre-send checks and frozen evidence. Unsupported settings fail validation. Existing live enablement and recipient controls still apply.

The same recipient/location lock and pending-intent guard apply across policies. Delivery keys and frozen comparison metadata record the selected version. Latest-baseline reads and historical replay verification accept both supported versions; changing policy does not discard delivery history. Malformed newest evidence fails closed instead of falling back to an older daily message.

## Validation

Targeted regression before adapter integration: 273 passed, one existing warning. Full-suite result is recorded after completion below. Tests use disposable local PostgreSQL schemas and mocked LINE; remote provider connections are blocked by the test runner.

New cases cover urgent cooldown bypass, the two-hour boundary, probability-only suppression, accepted v2 evidence, follow-up events, cross-policy duplicate prevention, concurrent workers, unknown/tampered history, invalid policy, shared preview/live configuration, and ambiguous-send pending intent after a policy change.

## Production evidence

See `P1_14_SCHEDULER_LOGS.json` and `P1_14_PRODUCTION_AUDIT.json` for timestamped evidence. Before the release below, production remained P1-12 / v1. At that recorded audit, scheduler and live flags were enabled for one existing recipient; 13 automatic ticks ran from 18:43 through 21:43 Bangkok with no failed refreshes, including three hourly refreshes. One tick suppressed identical content and twelve suppressed no significant change.

The read-only audit also exercised production delivery with `dry_run=True`, no LINE client and no delivery writes: source 44 suppressed for no significant change. There were zero intraday accepted deliveries and zero pending intents at that audit. Positive real intraday LINE acceptance and receipt on the handset remain unverified. A mocked accepted delivery proves the code path, not an actual provider or handset outcome.

No production forecast, event, recipient, scheduler or threshold was fabricated or changed to force a positive send. No station collector is required by or added to this task.

## Completed full regression

Command: `python weather-p112-tests.py -m "not integration" -q` using the private isolated test wrapper. Result: **493 passed, 18 external integration cases deselected, one existing `python_multipart` PendingDeprecationWarning**, pytest 329.34 seconds, process exit 0. No real LINE request was sent by this validation. `git diff --check` passed; the review index was empty and HEAD remained `c7fe95e1cc31c63cb689ade4b8d2d1ccbeabdfad`. All 34 protected dirty files in the original worktree retained their checkpoint hashes, original branch and HEAD, with an empty original index.

## Authorized production release (2026-10-10)

The user authorized deploy, commit and push. Code commit `eec1d7b7174f6b455a6934bf0d26218f1f391ee5` was ordinarily pushed to `review/p1-intraday-20261010`, authenticated through GitHub CLI, and independently verified through the GitHub API. No default-branch merge or force push was performed.

A sanitized API export from that exact commit was deployed to the existing Railway API service. Deployment `08eda3b9-d345-40d3-8f75-cff4ff0b5eb3` reached `SUCCESS`. Effective `INTRADAY_POLICY_VERSION` is now `intraday-v2-candidate`; live delivery and the scheduler are enabled for the same one authorized recipient. Runtime verification found zero mismatches across 71 app/alembic Python files. Internal and public health returned HTTP 200. Schema remains 0007, both intent unique indexes are present, and the prior daily baseline is retained. Daily cron deployment is unchanged; no new service or migration was added.

The first native tick after release ran at 22:06:40 Bangkok: complete, processed one recipient, no failed refresh, no truncation, and skipped for `short_window`. The matching production dry-run at 22:06:20 also skipped for `short_window` without a LINE client. This is the late-day coverage gate: fewer than two full comparison hours remain. It is not proof of a positive provider acceptance. At verification there were zero intraday accepted deliveries and zero pending intents; handset receipt remains unverified.

See `P1_14_PRODUCTION_RELEASE.json` and `P1_14_RELEASE_SCHEDULER_LOGS.json`. Earlier P1-14 audit files are retained as pre-release evidence.

Rollback: retain this new code and redeploy the API with `INTRADAY_POLICY_VERSION=intraday-v1` to restore the previous policy while continuing to recognize v2 history. To stop live sends, set `INTRADAY_SEND_ENABLED=false` and redeploy the same service. Do not reset pending intents, delete evidence or downgrade the history reader after v2 acceptance.
