# Vendored coding skills

Upstream skill folders are copied without content changes. Project-specific
routing lives in the root `AGENTS.md`, which implements the user's preference
for Ponytail full, standard Caveman response style, and selective Superpowers.

| Source | Version | Commit | Included |
| --- | --- | --- | --- |
| https://github.com/DietrichGebert/ponytail | v5.3.3 | 7801d061243d7b753bad0e0b3c057cd250b11755 | skills/ponytail |
| https://github.com/obra/superpowers | v7.0.1 | 2ce8aa15d05bd57213e6f746f953aafb7ded7a8b | systematic-debugging, test-driven-development, writing-plans, verification-before-completion, receiving-code-review |
| https://github.com/JuliusBrussee/caveman | pinned commit | 9b68f7ed12b05e7efaff18e65c5a3fc2849fd0a4 | skills/caveman/SKILL.md (standard voice only) |

Ponytail and Superpowers MIT license texts are preserved under `.agents/licenses/`.
The Caveman snapshot contains root Apache-2.0 and MIT license files; both are
retained as `caveman-Apache-2.0.txt` and `caveman-MIT.txt`. Only the standalone
standard voice instruction is vendored; proxy, engine, CLI, hooks, and alternate
voice skills are not included. Supporting files in
selected upstream skill folders are preserved. The always-on `using-superpowers`
dispatcher and automatic delegation workflows are intentionally excluded.

Updates: review a specific upstream release, copy the selected folders and
licenses, update this manifest, check referenced files and metadata, and review
the Git diff. Do not auto-update or fetch new versions during task startup.
