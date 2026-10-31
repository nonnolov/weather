# Vendored coding skills

Upstream skill folders are copied without content changes. Project-specific
routing lives in the root `AGENTS.md`, which implements the user's preference
for Ponytail full and selective Superpowers.

| Source | Version | Commit | Included |
| --- | --- | --- | --- |
| https://github.com/DietrichGebert/ponytail | v5.3.3 | 7801d061243d7b753bad0e0b3c057cd250b11755 | skills/ponytail |
| https://github.com/obra/superpowers | v7.0.1 | 2ce8aa15d05bd57213e6f746f953aafb7ded7a8b | systematic-debugging, test-driven-development, writing-plans, verification-before-completion, receiving-code-review |

MIT license texts are preserved under `.agents/licenses/`. Supporting files in
selected upstream skill folders are preserved. The always-on `using-superpowers`
dispatcher and automatic delegation workflows are intentionally excluded.

Updates: review a specific upstream release, copy the selected folders and
licenses, update this manifest, check referenced files and metadata, and review
the Git diff. Do not auto-update or fetch new versions during task startup.
