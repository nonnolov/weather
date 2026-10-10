# GitHub review package: durable rain evidence and intraday previews

Prepared 2026-10-10 Asia/Bangkok under user authorization to commit and push.
Target private repository: nonnolov/weather.
Review branch: review/p1-intraday-20261010.
Base: fc3d29c5203916a26e3c6c0a33f3712cc263da2e (feature/frontend-ux).

## Scope

Packages 33 existing P0/P1 runtime, test and handoff files plus this document.
P0 interval semantics and durable frozen delivery evidence are necessary
dependencies of the P1 comparator, baseline reader, shared locks, intraday
formatter/delivery helper and committed-snapshot preview CLI.
P1-07 is the current refresh-readiness review, not another runtime activation.

The existing daily sender adds the shared recipient/location lock, retaining
its daily key and existing schedule. P1 live delivery requires an explicitly
injected sender and dry_run=False; the new CLI offers preview only.
No ingestion route, scheduler, production configuration or LINE client is
automatically connected to the new intraday pipeline.

Excluded: docs/FRONTEND_RELEASE_20261010.md, an unrelated frontend release note.
No new frontend runtime changes, .env, credential files or generated output
were selected. The selected files passed a targeted credential-pattern scan.
Legacy unchanged tracked configuration is inherited from the existing base;
this package is not a full repository/history secret audit.

## Preservation and validation

An isolated worktree was created at:
C:\Users\Nutchanon\source\repos\weather-p1-review-20261010

Original working tree:
C:\Users\Nutchanon\source\repos\weather
All 34 original dirty files were SHA256-checkpointed and copied byte-for-byte
where selected. The original working branch/index/HEAD remain unchanged;
the source working tree stays dirty intentionally. Further development there
must account for the review branch rather than committing the same package twice.

Latest executed runtime result is the P1-06 isolated run: 268 passed, 1 existing
Starlette python_multipart warning, no skips. See P1_06_PREVIEW_HANDOFF.md for
the exact runner, PG isolation and cleanup. Tests were not repeated solely
because files were copied into a Git worktree. Pre-commit whitespace and Python
syntax checks are run on the review package, and staged paths are allowlisted.

## Push and production boundary

Fresh Railway GraphQL deploymentTriggers reads returned empty edges and
hasNextPage=false for API, cron and Hermes in production before this push.
Project 71e0e499-6a9d-46c5-a552-b9a9da0e1928;
environment 7ca11e27-30cd-4217-a80d-0b1647cb55c9.
The GitHub repository default branch is phase-1-backend-foundation.
This push targets a new review branch; it does not update either existing
feature/frontend-ux or phase-1-backend-foundation. No force push or merge.

P1-07 confirms production snapshot freshness and a compatible current-location
frozen baseline are still missing. Normal October 11 daily acceptance evidence,
a reviewed post-commit preview bridge, actual cadence/budget and ambiguity
handling remain relevant before live intraday activation. GitHub storage is not
deployment or alert readiness.

The commit identity and authoritative branch tip are available in Git history.
After push, the remote branch SHA must equal the local commit and original
source hashes/branch/index must still match their checkpoint.
