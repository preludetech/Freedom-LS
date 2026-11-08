# fls-dev (`fls-dev`) plugin

FreedomLS product-specific development tooling for Claude Code. Everything here is tied to how *this*
product works: multi-tenant / site-aware conventions, the custom user model, registration, markdown
content, admin, icons, brand, the FLS-specific SDD steps, and the downstream-distribution machinery.
Portable stack conventions live in the `ds` (django-stack) plugin, and the generic SDD workflow lives
in `sdd`. Where a portable skill carried an FLS-specific layer, `fls-dev` keeps a **thin overlay
skill** that references the `ds` (or `sdd`) skill and adds only the FLS delta.

Manifest name: `fls-dev`. Namespace: `/fls-dev:*`, `Skill(fls-dev:*)`. Config dir: `.claude/fls-dev/`.

`fls-dev` depends on `sdd` at runtime: its FLS-specific SDD steps spawn the `sdd` plugin's
`sdd:sdd-worker` / `sdd:sdd-mechanic` agents, and read `sdd`'s `commands/protected/*` helpers by path.

## What's inside (counted from disk)

### Skills (18)

FLS-specific: `domain-glossary`, `educator-interface`, `file-storage`, `icon-usage` (+2 resources), `markdown-content`,
`multi-tenant`, `notifications`, `panel-framework`, `registration`.

Thin overlays (reference the `ds`/`sdd` skill, add only the FLS delta): `admin-interface`, `alpine-js`,
`app-settings`, `frontend-styling`, `playwright-tests`, `template`, `testing`, `use-playwright`
(all → `ds:*`), and `git-worktree-setup` (→ `sdd:git-worktree-setup`).

### Commands (9 files)

Top level: `init`, `update_claude_plugin_fls_content`, `update_concrete_projects`
(run from the FLS `main` worktree: integrates completed specs into each concrete project listed in
`.claude/fls-dev/config.local.md`), `update_product_docs`, `update_upgrade_notes`.
`concrete/`: `README`, `update_fls`.
`protected/`: `design_check`, `frontend_check` (helpers read by path, not advertised as slash commands).

The three `update_*` commands (`update_upgrade_notes`, `update_product_docs`,
`update_claude_plugin_fls_content`) run as hooks of `/sdd:document`: `## Documentation Hooks` in
`.claude/sdd/config.md` names them as skills (`fls-dev:update_upgrade_notes`, …), after
`ds:app_map`. They stay runnable alone. They produce the upgrade notes for downstream projects, the
product docs under `docs/product/`, and the sync of the course-author plugin.

`/fls-dev:init` wires up only the `fls-dev` slice (its `enabledPlugins` key, its permissions, the
`.claude/fls-dev/` config dir, and its dev/DB wrapper scripts) and detect-and-skips the `ds`-owned
shared artifacts (root `claude.sh`, `SessionStart` hook, `.gitignore` `settings.local.json` line). It
also migrates a legacy `.claude/fls/` config dir **per file**: it moves what has no counterpart,
deletes only byte-identical duplicates, and preserves both sides of any conflict as a `.legacy`
copy rather than merging. `ds`-owned wrappers the legacy dir carried are relocated to
`.claude/ds/scripts/` without editing their contents, and `FLS_PATH` → `PLUGINS_ROOT` plus the
`fls`-era header comments are rewritten in this plugin's own wrappers. `/ds:init` must run first;
preflight enforces it, and nothing is written until every check passes.

### Scripts (7)

`dev_db_delete.sh`, `dev_db_init.sh`, `install_dev.sh` — per-branch dev/test database
setup and teardown.
`rebuild_after_rebase.sh` — dependency and database rebuild after a rebase.
`concrete_pointer_move.sh`, `concrete_projects.sh`, `concrete_rollback.sh` — the concrete-project
integration run.

The project's `.claude/settings.json` allow-list names every script under `.claude/ds/scripts/`
and `.claude/fls-dev/scripts/` so they run prompt-free during a QA session. **Adding a script
there and listing it is equivalent to granting it prompt-free execution with arbitrary arguments
in every QA session.** Review any new script with the same care as a new allow-list entry: confirm
it validates its arguments, does not write outside the project, and does not execute its
arguments as shell code.

### Resources (15)

FLS-specific: `email_templates`, `markdown_content`, `multi_tenant`, `concrete_spec_integration`
(the per-spec integration procedure a concrete project follows; `concrete/update_fls` follows it).
Plan review briefs, reached through `## Plan Review Hooks`: `plan_review_structure`,
`plan_review_fls_threats`.
FLS delta addenda (extend the matching `ds` resource): `admin_interface` (extends `ds`'s
`admin_unfold` + `admin_guardian`, the pair FLS's config selects), `factory_boy`, `frontend_styling`,
`qa_data_helper` (the conventions `sdd:qa-data-helper` reads), `templates_and_cotton`, `testing`,
`playwright-testing`.
`launcher_editing` and `wrapper_script_migration` (copies of the procedures `/fls-dev:init` follows).

### Templates

`config.md`, `config.local.md` (config templates `/fls-dev:init` copies into `.claude/fls-dev/`), and
`wrapper_scripts/` (`dev_db_delete.sh`, `dev_db_init.sh`, `install_dev.sh`,
`rebuild_after_rebase.sh`). The shared `claude.sh` launcher and the `settings.json` baseline are
`ds`-owned templates.
