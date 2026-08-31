# fls-dev (`fls-dev`) plugin

FreedomLS product-specific development tooling for Claude Code. Everything here is tied to how *this*
product works — multi-tenant / site-aware conventions, the custom user model, registration, markdown
content, admin, icons, brand, the FLS-specific SDD steps, and the downstream-distribution machinery.
Portable stack conventions live in the separate `ds` (django-stack) plugin, and the generic SDD
workflow lives in `sdd`. Where a portable skill carried an FLS-specific layer, `fls-dev` keeps a **thin
overlay skill** that references the `ds` (or `sdd`) skill and adds only the FLS delta — no duplicated
content.

Manifest name: `fls-dev`. Namespace: `/fls-dev:*`, `Skill(fls-dev:*)`. Config dir: `.claude/fls-dev/`.

`fls-dev` depends on `sdd` at runtime: its FLS-specific SDD steps spawn the `sdd` plugin's
`sdd:sdd-worker` / `sdd:sdd-mechanic` agents, and read `sdd`'s `commands/protected/*` helpers by path.

## What's inside (counted from disk)

### Skills (13)

FLS-specific, moved whole: `icon-usage` (+2 resources), `markdown-content`, `multi-tenant`,
`registration`.

Thin overlays (reference the `ds`/`sdd` skill, add only the FLS delta): `admin-interface`, `alpine-js`,
`app-settings`, `frontend-styling`, `playwright-tests`, `template`, `testing`, `use-playwright`
(all → `ds:*`), and `git-worktree-setup` (→ `sdd:git-worktree-setup`).

### Commands (9 files)

Top level: `init`, `do_qa`, `plan_security_review`, `plan_structure_review`,
`update_claude_plugin_fls_content`, `update_product_docs`,
`update_upgrade_notes`.
`concrete/`: `README`, `update_fls`.

`/fls-dev:init` wires up only the `fls-dev` slice (its `enabledPlugins` key, its permissions, the
`.claude/fls-dev/` config dir, and its dev/DB wrapper scripts) and detect-and-skips the `ds`-owned
shared artifacts (root `claude.sh`, `SessionStart` hook, `.gitignore` `settings.local.json` line). It
also migrates a legacy `.claude/fls/` config dir **per file** — moving what has no counterpart,
deleting only byte-identical duplicates, and preserving both sides of any conflict as a `.legacy`
copy rather than merging. `ds`-owned wrappers the legacy dir carried are relocated to
`.claude/ds/scripts/` without editing their contents, and `FLS_PATH` → `PLUGINS_ROOT` plus the
`fls`-era header comments are rewritten in this plugin's own wrappers. `/ds:init` must run first —
preflight enforces it, and nothing is written until every check passes. The FLS-specific SDD-step
commands spawn `sdd`-plugin agents.

### Agents (2)

`qa-data-helper` — creates QA test data with factory_boy factories. Its persistent memory lives at
`.claude/agent-memory/fls-dev-qa-data-helper/`.
`qa-bugfixer` — fixes one QA-reported bug TDD-style (failing test → fix → full suite → commit).
Spawned by `do_qa`'s triage loop.

### Scripts (9)

`dev_db_delete.sh`, `dev_db_init.sh`, `db_recreate.sh`, `install_dev.sh` — per-branch dev/test database
setup and teardown.
`qa_cleanup.sh`, `qa_collect_screenshots.sh`, `compress_screenshots.sh` + `compress_screenshots.py`,
`delete_sdd_work_files.sh` — QA-run artifact cleanup, screenshot collection and compression, and
scratch-file teardown. They live here rather than in `sdd` because `${CLAUDE_PLUGIN_ROOT}` is
per-plugin and their only callers are the `fls-dev` commands `do_qa` and `update_product_docs`.

### Resources (10)

FLS-specific: `email_templates`, `markdown_content`, `multi_tenant`.
FLS delta addenda (extend the matching `ds` resource): `admin_interface` (extends `ds`'s
`admin_unfold` + `admin_guardian`, the pair FLS's config selects), `factory_boy`, `frontend_styling`,
`templates_and_cotton`, `testing`, `playwright-testing`.
`agent_memory_guidelines` (a copy — the canonical home is the `sdd` plugin; duplicated here because
`${CLAUDE_PLUGIN_ROOT}` is per-plugin and `qa-data-helper` reads it).

### Templates

`fls.md`, `fls.local.md` (config templates `/fls-dev:init` copies into `.claude/fls-dev/`), and
`wrapper_scripts/` (`dev_db_delete.sh`, `dev_db_init.sh`, `db_recreate.sh`, `install_dev.sh`,
`qa_cleanup.sh`, `qa_collect_screenshots.sh`, `compress_screenshots.sh`,
`delete_sdd_work_files.sh`). The shared `claude.sh` launcher and the `settings.json` baseline are
`ds`-owned templates.
