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

# Upgrade notes: sdd-improve

This change touches only the Claude Code plugins under `claude_plugins/` (`sdd`, `fls-dev`,
`django-stack`). No Django code, model, template, setting, Python package, npm package or Tailwind
source changed. A downstream project that does not use the plugins has nothing to do.

## Breaking changes

These slash commands are removed. Use the replacement instead:

| Removed | Use instead |
|---|---|
| `/sdd:next` | Open the spec's `todo.md` and run the next `(cmd)` item yourself |
| `/sdd:improve_idea` | `/sdd:spec_from_idea`, which now researches the idea before writing the spec |
| `/ds:threat-model` | The `new_threats` dimension of `/sdd:plan_from_spec`'s plan review |
| `/fls-dev:plan_security_review` | The same `new_threats` dimension, plus the `FLS threats` plan review hook |
| `/fls-dev:plan_structure_review` | The `Structure` plan review hook, run by `/sdd:plan_from_spec` |
| `/ds:security-review` | Bandit in pre-commit, and Claude Code's built-in `/security-review` for ad hoc reviews |
| Running `/ds:app_map`, `/fls-dev:update_upgrade_notes`, `/fls-dev:update_product_docs` and `/fls-dev:update_claude_plugin_fls_content` one by one | `/sdd:document`, which runs every skill under `## Documentation Hooks` in order. Each one still runs alone. |

`.claude/sdd/config.md` gains five sections the plugins now read: `## Plan Review Hooks`,
`## Review Hooks`, `## Documentation Hooks`, `## QA Hooks` and `## PR Hooks`. A missing section is
treated as "no hooks", so nothing fails. But with these sections missing, `/sdd:plan_from_spec`
skips the FLS structure and threat briefs, the per-batch review in `/sdd:implement_plan` skips the
comment and test standards, `/sdd:document` does nothing, and new `todo.md` checklists say "Execute
the QA plan by hand" instead of naming `/fls-dev:do_qa`.

`/ds:init` no longer reads the legacy `FLS_PATH` variable from `.claude/*/scripts/*.sh` when it works
out `PLUGINS_ROOT`. It reads the `PLUGINS_ROOT="…"` line in `claude.sh` first, so a project whose
launcher has that line is unaffected. `/fls-dev:init` still accepts `FLS_PATH` and migrates it.

## Manual steps

1. Run `/sdd:init`. It adds the five new sections to `.claude/sdd/config.md` with blank values and
   keeps every existing value.
2. Run `/fls-dev:init`. If a key is blank or a list is empty, it fills in:
   - `## Plan Review Hooks`: `Structure` and `FLS threats`, which point at
     `claude_plugins/fls-dev/resources/plan_review_structure.md` and
     `claude_plugins/fls-dev/resources/plan_review_fls_threats.md`.
   - `## Review Hooks`: `Test standard` → `claude_plugins/fls-dev/skills/testing/SKILL.md`.
     `Comment standard` → `.claude/skills/code-comments/SKILL.md`, set only if that file exists in
     your project. If it doesn't, the key stays blank and that half of the batch review is skipped.
   - `## Documentation Hooks`: `ds:app_map`, `fls-dev:update_upgrade_notes`,
     `fls-dev:update_product_docs`, `fls-dev:update_claude_plugin_fls_content`, in that order.

   These paths get your `PLUGINS_ROOT` prefix when the plugins live in a subdirectory.
3. `/fls-dev:init` does not fill the two remaining keys. Set them by hand in
   `.claude/sdd/config.md`:
   - `## QA Hooks` → `- QA command: fls-dev:do_qa`
   - `## PR Hooks` → `- Fetch PR comments: .claude/ds/scripts/fetch_pr_comments.sh` (`/ds:init`
     installs this wrapper). If you leave it blank, `/sdd:address_pr_review` fetches comments
     with `gh` instead.
4. The `todo.md` checklists of specs that were already in progress keep the old template. Skip any
   item that names a removed command. New specs get the shorter template from `/sdd:start`.
5. Remove permission entries in `.claude/settings.json` that name the removed commands, if you
   added any.
