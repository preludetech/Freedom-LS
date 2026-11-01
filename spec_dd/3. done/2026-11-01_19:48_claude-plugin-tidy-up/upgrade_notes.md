---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: claude-plugin-tidy-up

No Django code, model, template, setting or package changed. Everything below concerns the Claude
Code plugins under `claude_plugins/` and the per-project `.claude/` configuration that downstream
projects keep for them.

## Breaking changes

Skills that lived in FLS's `.claude/skills/` now ship in plugins, under namespaced names:

| Old | New | Path |
|---|---|---|
| `answer` (`/answer`) | `productivity:answer` (`/productivity:answer`) | `claude_plugins/productivity/skills/answer/SKILL.md` |
| `unslop` | `productivity:unslop` | `claude_plugins/productivity/skills/unslop/SKILL.md` |
| `writing-for-agents` | `productivity:writing-for-agents` | `claude_plugins/productivity/skills/writing-for-agents/SKILL.md` |
| `code-comments` | `ds:code-comments` | `claude_plugins/django-stack/skills/code-comments/SKILL.md` |
| `domain-glossary` | `fls-dev:domain-glossary` | `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` |
| `notifications` | `fls-dev:notifications` | `claude_plugins/fls-dev/skills/notifications/SKILL.md` |

The planning-document rules that used to sit in `code-comments` are now `sdd:planning-references-in-code`.

- **New `productivity` plugin, and `sdd` now depends on it.** `sdd` calls `productivity:unslop`.
  A project that loads `sdd` must also load `productivity`.
- **QA moved from `fls-dev` to `sdd`.** `/fls-dev:do_qa` is now `/sdd:do_qa`. The QA agents are
  `sdd:qa-bugfixer` and `sdd:qa-data-helper`. The QA data helper's agent memory moved from
  `.claude/agent-memory/fls-dev-qa-data-helper/` to `.claude/agent-memory/sdd-qa-data-helper/`.
- **QA values moved config files.** QA credentials and dev-data commands now live in
  `.claude/sdd/config.md` under `## QA Login` and `## QA Dev Data`, with the QA hooks and
  `## Testing Skills`. They are no longer read from `.claude/fls-dev/config.md`.
- **The `.claude/fls-dev/scripts/` QA wrappers are gone.** `qa_cleanup.sh`,
  `qa_collect_screenshots.sh`, `compress_screenshots.sh` and `delete_sdd_work_files.sh` now run
  directly from `claude_plugins/sdd/scripts/`.
- **Old `.claude/skills/` paths in config are stale.** A `Comment standard` entry under
  `## Review Hooks`, or a `## Vocabulary Sources` entry, in `.claude/sdd/config.md` that still
  points at `.claude/skills/code-comments/SKILL.md` or `.claude/skills/domain-glossary/SKILL.md`
  points at a file that is no longer there.

## Manual steps

1. Add `productivity` to the project's launcher and settings: run `/productivity:init`.
   `/sdd:init` lists it as an outstanding action when `claude.sh` lacks the plugin.
2. Run `/sdd:init`. It adds the `.claude/settings.json` allow entries for the scripts that now run
   from `claude_plugins/sdd/scripts/`; without them every QA script call prompts.
3. Run `/fls-dev:init`. It sets `QA command` to `sdd:do_qa` and fills the other `## QA Hooks`
   keys. It copies `## Dev Credentials`, `## Project Settings` and `## QA Dev Data` from
   `.claude/fls-dev/config.md` into `.claude/sdd/config.md`, removes those sections once every
   value is copied, and fills any `## QA Login` or `## QA Dev Data` key still blank with the FLS
   dev default. It re-points a `Comment standard` that names the old `code-comments` path. It
   also lists any `.claude/settings.json` allow entries that still name the removed
   `.claude/fls-dev/scripts/` QA wrappers, and any such wrapper (`qa_cleanup.sh`,
   `qa_collect_screenshots.sh`, `compress_screenshots.sh`, `delete_sdd_work_files.sh`) still under
   `.claude/fls-dev/scripts/`. Delete those files yourself: their target moved, so they no longer
   run.
4. By hand, re-point a `## Vocabulary Sources` entry naming
   `.claude/skills/domain-glossary/SKILL.md` to
   `<PLUGINS_ROOT>/claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`. No init command does this.
5. Replace `/answer` with `/productivity:answer`, and any bare skill name from the table above
   with its namespaced name, in the project's own commands, skills, `CLAUDE.md` and settings
   allow entries.
6. If the project kept its own QA data-helper memory under
   `.claude/agent-memory/fls-dev-qa-data-helper/`, move it to
   `.claude/agent-memory/sdd-qa-data-helper/`.
