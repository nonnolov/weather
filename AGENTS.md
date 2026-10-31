# WeatherNow coding instructions

## Default: Ponytail full

For coding, debugging, refactoring, code review, and dependency decisions, read
`.agents/skills/ponytail/SKILL.md` and apply its full level. Solve the whole task
with the smallest complete change, existing project patterns, and existing
libraries. Keep replies concise; report material limits and checks actually run.
The user does not need to mention Ponytail in each prompt.

## Default response style: Caveman

For coding tasks and their progress reports, also read
`.agents/skills/caveman/SKILL.md`. Use its standard concise voice automatically;
the user does not need to request it each time. Reply in the user's language
(Thai in this project conversation). Keep explanations readable and preserve
technical facts, uncertainty, negations, numbers, units, commands, paths, errors,
and test results. Never promise a fixed token reduction.

Caveman controls chat prose. Ponytail controls implementation scope; selective
Superpowers controls the workflow. Keep persisted code, comments, documentation,
commit messages, and PR descriptions in normal clear prose. Give full sentences
when explaining risky actions, ordered instructions, or user confusion. Requests
for a detailed explanation override compression for that answer. Honor an
explicit request to stop Caveman for the rest of the session.

Only standard Caveman is installed. Its references to ultracave, megacave, or
compression skills do not install those variants. If requested, report their
absence instead of pretending to activate them. No hook-backed mode tracking is
configured; status must reflect the conversation, not an inferred stored value.

## Selective Superpowers

Use the following repository skills only when their conditions apply. This is
the user's explicit routing preference and takes precedence over broader skill
instructions about always loading skills or automatically chaining workflows.

| Condition | Read |
| --- | --- |
| Unexplained failure, recurring bug, or unexpected behavior needing investigation | `.agents/skills/systematic-debugging/SKILL.md` |
| Meaningful new behavior or a bug fix that benefits from a regression test | `.agents/skills/test-driven-development/SKILL.md` |
| Substantial work across several components, such as an API migration | `.agents/skills/writing-plans/SKILL.md` |
| Before claiming an implementation is fixed, complete, or passing | `.agents/skills/verification-before-completion/SKILL.md` |
| Evaluating technical code review feedback | `.agents/skills/receiving-code-review/SKILL.md` |

For references written as `superpowers:<name>`, resolve the name to the matching
`.agents/skills/<name>/SKILL.md` above. This installation intentionally includes
only these five Superpowers skills. If another referenced workflow is absent,
continue inline with the available tools and report a material limitation;
do not claim to have loaded a missing skill.

For typos, documentation, formatting, simple configuration, and clear small
edits, apply Ponytail with proportionate checks. Do not impose a separate design
approval, elaborate plan, TDD cycle, or agent delegation on those tasks. For
larger tasks, use a concise plan and proceed within the user's existing
authorization. Ask only for a genuinely missing consequential decision.

Do not spawn subagents unless the user explicitly requests delegation. Skill
suggestions to delegate do not override this preference. Use ordinary inline
execution when no delegation has been requested.

## Project context and verification

Read `docs/BRANCH_WORKFLOW.md` before changing branches or integrating work.
Use a feature or fix branch. Preserve existing API contracts, forecast data
integrity, authentication, validation, and error handling. Inspect actual
Cloudflare migration files and handoffs before inferring the active runtime
from older documentation.

Run checks appropriate to the changed behavior and report their actual results.
Use the integration checks required by `docs/BRANCH_WORKFLOW.md` before merging.
For instruction-only changes, check paths, skill metadata, source integrity,
and the diff; application tests are not evidence of agent skill activation.
Never claim staging or production verification from local checks. Use isolated
test data for database checks and prevent tests from sending real LINE messages.

## Cloud setup

These repository skills require no lifecycle hooks or runtime skill downloads.
Start tasks at the repository root and read this file first. If skills are not
listed by discovery, read their explicit paths and report the discovery issue.
See `docs/CODEX_CLOUD_SETUP.md` for publishing and smoke checks.
