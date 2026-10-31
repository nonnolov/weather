# WeatherNow Codex Cloud setup

This branch prepares repository skills for a new cloud environment. It does not
change Windows Codex settings or repair the Windows Ponytail hook failure.

## Files and behavior

- Root `AGENTS.md`: Ponytail full for coding; standard Caveman response style; selective Superpowers routing.
- `.agents/skills/`: one Ponytail skill, one standard Caveman skill, and five Superpowers skills with their
  upstream supporting files. Skill discovery uses repository-local paths.
- `.agents/SOURCES.md` and `.agents/licenses/`: exact versions, commits, licenses.

No lifecycle hook, Node launcher, global `config.toml`, skill installer, or
network download is needed to load these instructions. Skills on the Windows
computer are separate from this cloud setup.

## Apply to a cloud environment

1. Use the branch containing this change, or integrate it through the project's
   normal PR workflow before preparing an environment from `main`.
2. In Settings > Codex Cloud > Environments, create an environment for
   `nonnolov/weather`, or edit the intended environment.
3. Paste the setup request below into its setup conversation. Let Codex inspect
   the actual repository and prepare application dependencies and isolated test
   services. Put credentials in environment settings; do not commit them.
4. Review setup results, save, and Publish or Republish. Start a new task from
   that published environment. Existing tasks keep their own working state.

### Setup request

```text
Prepare this cloud environment for nonnolov/weather using this repository's
AGENTS.md. Preserve the existing application setup and inspect current migration
handoffs before deciding which runtimes and dependencies are needed.

Keep Ponytail v5.3.3 full as the default for coding. Use only the five vendored
Superpowers v7.0.1 skills when the routing table in AGENTS.md matches the task.
Load .agents/skills/caveman/SKILL.md for concise chat responses in the user's
language. Keep technical payloads verbatim and persisted artifacts in normal
clear prose. Honor requests for detail or to stop Caveman. Only standard Caveman
is installed; do not activate absent ultracave or megacave variants.
Do not install lifecycle hooks or copy Windows user configuration. Do not install
an always-on Superpowers dispatcher or enable automatic agent delegation.

Check that all seven .agents/skills/*/SKILL.md files and their supporting files are
readable. Preserve their pinned source versions and licenses. Detect and report
any duplicate skill names supplied by account plugins; prefer the explicitly
referenced repository versions for this project without disabling unrelated
account plugins.

Prepare the Install script for application dependencies based on the actual
repository. In the Start skill, instruct each new task to start at the repository
root, read AGENTS.md, then load Ponytail for coding, standard Caveman for chat
style, and the relevant Superpowers skill only when its routing condition
applies. Load skills by their explicit paths if discovery is unavailable and report that fallback.

Use local or isolated test services; do not run production database migrations,
send real LINE messages, or deploy merely as an environment readiness check.
Report the exact checks and blockers, then leave the environment ready to publish.
```

## New-task smoke checks

After publishing, start a new task and ask:

```text
Read AGENTS.md and inspect the seven repository skills without changing application
files. Report the paths you loaded, the Ponytail default level, the Caveman
response style and language policy, and which
Superpowers skill you would select for each of these: (1) a README typo,
(2) a recurring API 500, (3) a migration across multiple API components,
(4) a meaningful behavior change with a regression test, (5) code review feedback.
Explain what evidence is needed before claiming an implementation is complete.
Also explain how you preserve exact commands and errors, handle a request for
detail or to stop Caveman, and report absent ultra or wenyan variants.
Do not spawn agents or run production operations.
```

Expected routing: (1) Ponytail and a proportionate text check; (2) systematic
debugging; (3) writing plans; (4) TDD; (5) receiving code review. Before completion
claims about implementation, use verification-before-completion. Standard Caveman
compresses only chat prose, preserves the user's language and
exact technical strings, and yields to requests for detail or to stop. No
automatic delegation. This smoke check tests reported routing; actual skill use
still
requires observing the subsequent task's file reads and behavior.

## Validation scope

Repository validation can confirm pinned file contents, metadata, support paths,
and licenses. Successful publication and new-task discovery must be checked in
the target cloud environment. These files do not set cloud model selection or
transfer Windows authentication and service credentials.

## Official platform references

- https://learn.chatgpt.com/docs/environments/cloud-environments
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/plugins
