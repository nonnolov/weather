# Weather P0/P1 GitHub review package

Repository: private nonnolov/weather.
Review branch: review/p1-intraday-20261010.
Original working tree: C:\Users\Nutchanon\source\repos\weather.
Original branch/HEAD: feature/frontend-ux / fc3d29c5203916a26e3c6c0a33f3712cc263da2e.
Isolated worktree: C:\Users\Nutchanon\source\repos\weather-p1-review-20261010.

## Initial package scope (historical)

Local package commit 57eed054d29793af1f93fde231c4614007d73f42 contains the
reviewed P0 evidence foundation and P1-02 through P1-07 preparation. The
subsequent integration commit on this review branch adds P1-08 post-commit
preview, P1-09 controlled acceptance reports, P1-10 periodic preview preparation,
regression tests and current acceptance/capacity records. It does not change
production service configuration or activate any sender.

The original unrelated docs/FRONTEND_RELEASE_20261010.md is excluded. All 34
original dirty file hashes, original HEAD/branch and original empty index are
checked independently. Worktree packaging must not overwrite those files.

## Initial upload boundary (historical)

The user explicitly requested GitHub CLI, completion of the preparation and
ordered tests before commit/push, then authorized that sequence. gh verifies
the repository and configures the credential helper; git performs the actual
local commit and ordinary branch push. There is no force push, default-branch
update, merge, pull request, deployment or live intraday LINE activation.

Fresh pre-upload checks found zero GitHub repository hooks and zero Actions
workflows. A Railway public GraphQL query through the CLI confirmed empty
production deployment-trigger connections for API, cron and Hermes, with no
additional pages. The review branch was absent remotely before its first push.
Uploading this branch therefore does not wire a Railway deployment trigger.
Remote branch SHA must match the local SHA after upload; report that SHA and
GitHub branch link directly to the user, since a commit cannot store its own ID.

## Initial validation and remaining operations (historical)

See P1_ACCEPTANCE.md and P1_10_SCHEDULED_PREVIEW_HANDOFF.md for final test results,
controlled accepted daily evidence, cadence estimates, limits and rollout steps.
Local mocked tests plus the controlled daily baseline prove the prepared
preview pipeline; they do not prove automatic production execution.

Both preview flags remain false by default. The API contains no real intraday
sender wiring. Production deployment and enabling preview require the next
explicit rollout instruction. The normal daily cron's post-release scheduled
acceptance remains separate from October 10's controlled one-off acceptance.
No upgrade or paid dependency was introduced.

## Subsequent authorized production rollout

The user subsequently explicitly authorized deploying and enabling preview.
P1-11 deployed the exact 6eda58f source archive to the existing API service;
deployment 515a5c49-b042-4833-bd30-23ba3fef97ba reached SUCCESS. Production
settings now have both preview flags true, while their source defaults remain
false. Request-side and the first native timed preview were observed; neither
sent LINE or added delivery history. See P1_11_PRODUCTION_PREVIEW_HANDOFF.md.
This documentation update does not redeploy the code, change the daily cron,
add autodeploy triggers or enable a real intraday sender. The code-upload
boundary described above is historical; P1-11 is its separately authorized
API-only rollout. The documentation commit follows the deployed source commit.

## P1-12 review commit after authorized production rollout

The user subsequently explicitly authorized deploying P1-12 with live intraday
for the existing recipient, then requested commit and push to GitHub. This
review-branch update packages the already deployed runtime, additive migration
0007, all 19 new local regression cases, current acceptance and sanitized
production evidence. No unrelated original frontend changes are included.

Runtime identity: git baseline 39e4471 plus eight reviewed overlays was deployed
before this commit. Deployment bf7c1724-7445-4395-a40d-81056f8b80a9 reached SUCCESS;
all 68 deployed app/Alembic hashes match. Runtime files in this commit are
rechecked against that deployment checkpoint. Tests: 439 passed, 18 external
integration cases deselected, one existing warning. See P1_12_LIVE_DELIVERY_HANDOFF.md
and P1_12_PRODUCTION_LIVE.json.

Pre-upload checks on October 10 confirm private nonnolov/weather, the existing
review/p1-intraday-20261010 branch, remote base SHA 39e4471 matching local HEAD,
zero repository hooks, zero Actions workflows and zero production Railway
deployment-trigger connections for API, cron and Hermes (no additional pages).
GitHub CLI verifies auth/repo and configures Git credentials. Git stages only
the explicit P1-12 file allowlist, makes a local commit and performs an ordinary
push to that review branch. No default-branch update, force push or merge is
part of the upload, and no Railway deployment is triggered by this branch push.
The exact commit SHA and remote read-back verification are reported to the user
outside this commit because a commit cannot contain its own final identity.

Production live is already enabled for exactly one prior accepted recipient.
The native live tick suppressed identical_content without a LINE call. The
upload records that observed result; it does not manufacture a positive alert,
claim handset receipt or close the remaining P1 acceptance gates. Daily cron
source-linked acceptance, later hourly refresh and a positive real intraday
send remain separate observations.

Original 34 dirty-file hashes, feature/frontend-ux/fc3d29c HEAD and original
empty index are independently preserved. No original working-tree file is
staged or committed; all changes are in the isolated review worktree.
