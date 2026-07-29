# Notes: PR review + plugin naming, as input to the documentation steps

Written after reading the full `main..HEAD` diff (25 commits, 257 files) and every plugin manifest,
README, and `init` command on this branch. These notes exist to feed steps 10–13 of `todo.md`
(`/update_product_docs`, `/update_upgrade_notes`, `/update_template_repo`,
`/update_claude_plugin_fls_content`). They record what the names actually are on disk, not what the
spec proposed.

---

## 1. The naming scheme as shipped

Four plugins under a new top-level `claude_plugins/`. Three identifiers matter and they are **not**
all the same string:

| Directory (`claude_plugins/…`) | Manifest `name` | Namespace | Config dir | Agent-memory dir |
|---|---|---|---|---|
| `django-stack/` | `ds` | `/ds:*`, `Skill(ds:*)` | `.claude/ds/` | `.claude/agent-memory/code-reviewer/` |
| `fls-dev/` | `fls-dev` | `/fls-dev:*`, `Skill(fls-dev:*)` | `.claude/fls-dev/` | `.claude/agent-memory/fls-dev-qa-data-helper/` |
| `sdd/` | `sdd` | `/sdd:*`, `Skill(sdd:*)` | `.claude/sdd/` | — |
| `fls-content/` | `fls-content` | `/fls-content:*` | — | — |

**`django-stack` is the only case where the directory name and the manifest name differ.** For the
other three they are identical. The MCP server the `ds` plugin ships is exposed as
`mcp__plugin_ds_playwright__*` — i.e. Claude Code derives the tool prefix from the **manifest name**,
not the directory. That is the strongest live evidence available on this branch for which identifier
is the real one.

Two naming choices are worth documenting because they are not obvious:

- **`fls-dev`, not `fls`.** Spec §1 naming note: it disambiguates from the sibling `fls-content`
  plugin and signals *developer* tooling rather than course-authoring tooling. Every derived
  identifier moved with it — permission entries, config dir, agent-memory dir, agent prefix.
- **Directories are named after the plugin, not the mechanism** (commit `38d3fcaf`). The four
  directories previously carried `-claude-plugin` / `-plugin` suffixes restating what the parent
  `claude_plugins/` already says. `sdd-claude-plugin → sdd`, `django-stack-claude-plugin →
  django-stack`, `fls-dev-claude-plugin → fls-dev`, `fls-content-plugin → fls-content`. The inner
  `.claude-plugin/` manifest directory keeps its name (Claude Code requires it).

### 1.1 `enabledPlugins` key — inconsistency found and fixed

**Resolved. The key is `ds`.** Recorded here because the upgrade notes and the template repo both
have to write this key, and getting it wrong fails silently.

The `ds` plugin's own init instructions and settings template said `"django-stack": true` while
FLS's `.claude/settings.json` said `"ds": true`. The Claude Code plugins reference settles it — on
the manifest `name` field:

> Unique identifier (kebab-case, no spaces). When a marketplace entry lists the plugin under a
> different name, the marketplace entry name is what `enabledPlugins` keys and `/plugin` use

So `enabledPlugins` keys off the plugin **name**, never the directory. (The marketplace-entry
override doesn't apply — these are `--plugin-dir` local plugins with no marketplace.) This matches
the live evidence: the MCP server ships from `claude_plugins/django-stack/.mcp.json` but is exposed
as `mcp__plugin_ds_playwright__*`.

FLS's own settings.json was therefore already correct; the plugin was wrong. Fixed on this branch in
six places:

- `claude_plugins/django-stack/templates/settings.json` → `{"ds": true}`
- `claude_plugins/django-stack/commands/init.md` — the scope statement (§Ownership), the merge rule,
  the write step, the create-from-scratch fallback, and validation step 8.1
- `claude_plugins/sdd/commands/init.md` — the "never touch `django-stack`/`fls-dev` keys" warning now
  names `ds`

Path references to the `django-stack` **directory** (`--plugin-dir`, `claude_plugins/django-stack/`)
were left alone — they are correct. The `ds` README now states the `enabledPlugins` key explicitly
and warns that this is the one plugin where directory ≠ manifest name.

The bug predated the directory rename (it came in with the Workstream F cutover), so `38d3fcaf` did
not cause it. `sdd`, `fls-dev`, and `fls-content` were never affected — their directory and manifest
names are identical.

---

## 2. Rename inventory — the master table for upgrade notes

Everything below is a downstream-visible rename. This is the substance of the upgrade notes; nothing
here is FLS-internal-only.

| Kind | Before | After |
|---|---|---|
| Plugin root | `fls-claude-plugin/` | `claude_plugins/django-stack/` + `claude_plugins/fls-dev/` + `claude_plugins/sdd/` |
| Content plugin | `fls-content-plugin/` | `claude_plugins/fls-content/` |
| Manifest name | `fls` | split into `ds`, `fls-dev`, `sdd` |
| Skill namespace | `Skill(fls:*)` | `Skill(ds:*)`, `Skill(fls-dev:*)`, `Skill(sdd:*)` |
| Agents | `fls:sdd-worker`, `fls:sdd-mechanic` | `sdd:sdd-worker`, `sdd:sdd-mechanic` |
| Agent | `fls:qa-data-helper` | `fls-dev:qa-data-helper` |
| Agent | `fls:code-reviewer` | `ds:code-reviewer` |
| Agent memory | `.claude/agent-memory/fls-code-reviewer/` | `.claude/agent-memory/code-reviewer/` (unprefixed, generic) |
| Agent memory | `.claude/agent-memory/fls-qa-data-helper/` | `.claude/agent-memory/fls-dev-qa-data-helper/` |
| Config dir | `.claude/fls/` | `.claude/ds/` + `.claude/fls-dev/` + `.claude/sdd/` (split by owner) |
| Gitignored local config | `.claude/fls/config.local.md` | `.claude/ds/config.local.md`, `.claude/fls-dev/config.local.md`, `.claude/sdd/config.local.md` |
| Wrapper scripts | `.claude/fls/scripts/*.sh` | `.claude/ds/scripts/` (db_clear, fetch_pr_comments, find_available_port, kill_runserver) and `.claude/fls-dev/scripts/` (db_recreate, dev_db_delete, dev_db_init, install_dev) |
| Launcher sentinel | `FLS_PLUGIN=1` / `$FLS_PLUGIN` | `CLAUDE_PLUGINS_LOADED=1` / `$CLAUDE_PLUGINS_LOADED` |
| Launcher variable | `FLS_PATH` / `__FLS_PATH__` | `PLUGINS_ROOT` / `__PLUGINS_ROOT__` |
| MCP tool prefix | `mcp__plugin_fls_playwright__*` | `mcp__plugin_ds_playwright__*` |
| Init command | `/fls:init` (one command) | `/ds:init`, `/fls-dev:init`, `/sdd:init` (three, run in that order) |
| Deleted skill | `fls:request-code-review` | gone — use the `ds:code-reviewer` agent directly |

**Which scripts moved to which plugin** matters, because the split is by *ownership*, not
alphabetical: generic Django/dev-loop scripts went to `ds`, per-branch database scripts went to
`fls-dev`. A downstream project that hardcoded `.claude/fls/scripts/dev_db_delete.sh` now needs
`.claude/fls-dev/scripts/dev_db_delete.sh`, but `.claude/fls/scripts/kill_runserver.sh` becomes
`.claude/ds/scripts/kill_runserver.sh`. There is no single find-and-replace for the directory.

---

## 3. Draft manual-steps sequence for downstream projects

Ordered, because `/ds:init` owns the shared artifacts the other two detect-and-skip. Getting the
order wrong leaves a project with no `claude.sh`.

1. Pull FLS (submodule bump if consumed as a submodule).
2. Run `/ds:init` **first** — it creates/repairs the root `claude.sh`, the `SessionStart` hook, the
   `.gitignore` line, `.claude/ds/config.md`, and the `ds` wrapper scripts. It also performs the
   automated legacy migration: rewrites `FLS_PLUGIN`→`CLAUDE_PLUGINS_LOADED` and
   `FLS_PATH`→`PLUGINS_ROOT` in `claude.sh` and in existing wrapper scripts, replaces the single
   monolith `--plugin-dir` line with the `django-stack` one, rewords the "FLS PLUGIN NOT LOADED"
   hook message, and strips the legacy `CLAUDE.md` plugin-check line.
3. Run `/fls-dev:init` — migrates `.claude/fls/` → `.claude/fls-dev/` (via `git mv`, preserving
   `config.md`, `config.local.md`, and `scripts/`), rewrites `.claude/fls/scripts/…` permission
   literals in `settings.json`, and adds its own `--plugin-dir` line.
4. Run `/sdd:init` — adds its `enabledPlugins` key, `Skill(sdd:*)` permission, `.claude/sdd/config.md`
   (which needs the project's setup/teardown script paths filled in), and its `--plugin-dir` line.
5. Fill in the new config files by hand. `/ds:init` writes **portable defaults that are wrong for
   FLS-shaped projects**: `Admin theme: standard` (FLS uses `unfold`), `Object permissions: disabled`
   (FLS uses guardian), `Alpine CSP build`. `.claude/sdd/config.md` needs the worktree setup/teardown
   script paths.
6. If the project holds `claude_plugins/` somewhere other than its own root (the submodule case),
   set `PLUGINS_ROOT` in `claude.sh` — e.g. `submodules/Freedom-LS`.
7. Launch with `./claude.sh`, never bare `claude` — the `SessionStart` hook hard-stops the session
   otherwise.

**What the inits do *not* migrate automatically**, so upgrade notes must call it out as hand work:

- Project-authored `Skill(fls:*)` permission entries beyond the two literals `fls-dev:init` rewrites.
- Any project-local command, agent, skill, or `CLAUDE.md` prose that names `fls:sdd-worker`,
  `fls:sdd-mechanic`, `fls:qa-data-helper`, or `fls:code-reviewer`.
- Any hardcoded `fls-claude-plugin/` path in project docs, scripts, or CI.
- `mcp__plugin_fls_playwright__*` permission entries.
- Existing agent-memory directories: `fls-code-reviewer/` → `code-reviewer/` and
  `fls-qa-data-helper/` → `fls-dev-qa-data-helper/`. Not renaming them loses accumulated memory
  silently — the agent starts with an empty memory dir rather than erroring.
- `.gitignore`: one `config.local.md` line becomes three.

> Silent failure is the defining risk of this change. Claude Code performs no cross-plugin static
> validation (spec §2), so a missed rename surfaces as a command that isn't found or an agent that
> isn't spawned, often deep inside a fanned-out subagent. The upgrade notes should say this
> explicitly and recommend a grep sweep for `fls:`, `fls-claude-plugin`, `.claude/fls/`,
> `FLS_PLUGIN`, `FLS_PATH`, and `mcp__plugin_fls_` after running the three inits.

---

## 4. Draft `upgrade_notes.md` frontmatter, with the reasoning per flag

The schema in `/fls-dev:update_upgrade_notes` is built for Django-app changes (migrations, templates,
settings, packages). **This change fits none of those categories** — it touches no models, no
migrations, no runtime FLS behaviour (spec §1 is explicit). Nearly every flag is `false`, and the
whole payload lands in the prose sections. That is the honest answer, not a gap to pad.

```yaml
requires_migrations: false          # no model changes anywhere in the diff
requires_template_review: false     # no Django HTML template under freedom_ls/ changed
changed_template_paths: []
requires_settings_change: false     # config/ untouched; the pyproject.toml edits below are FLS-internal
changed_settings: []
requires_package_upgrade: false     # no dependency added/bumped
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false    # see below — judgement call
```

Two calls worth defending in the notes:

- **`requires_settings_change: false`.** `pyproject.toml` did change (`testpaths`, two ruff
  `per-file-ignores` paths, the mypy `exclude` regex) but every edit just re-points a path at
  `claude_plugins/`. Downstream projects keep their own `pyproject.toml` and never referenced
  `fls-content-plugin/`, so there is nothing to mirror. Say so rather than leaving it unexplained.
- **`requires_tailwind_rebuild: false`.** `tailwind.components.css` lost an empty
  `@layer utilities {}` block and `tailwind.input.css` had a stale comment corrected
  (`scripts/write-active-theme.mjs` → `manage.py write_active_theme_css`, matching the actual
  `_write_active_theme` npm script). Neither changes a byte of generated CSS. If the reviewer
  prefers belt-and-braces, flipping this to `true` costs one `npm run tailwind_build` — but the
  factual answer is that no rebuild is needed.

**The schema's blind spot:** none of these flags express "your developer tooling has been renamed and
you must re-run three init commands." Consider whether the prose sections carry it, or whether this
change justifies proposing a `requires_plugin_reinit`-style flag to the schema. Flag the gap for the
user rather than silently forcing the change into an ill-fitting field.

---

## 5. Notes for `/update_template_repo` (todo step 12)

**This step is almost certainly *not* a no-op**, which is unusual — most features leave the template
repo alone. The template repo carries exactly the files this change renames:

Per `claude_plugins/fls-dev/resources/template_repo_manifest.md`, the scaffold ships:

- `claude.sh` — commented "launches Claude with the FLS plugin loaded". It has the old single
  `--plugin-dir …/fls-claude-plugin` line, `FLS_PLUGIN=1`, and `FLS_PATH="submodules/Freedom-LS"`.
  All four need updating: three `--plugin-dir` lines, the new sentinel, the new variable name.
- `.claude/settings.json` — `enabledPlugins`, `Skill(fls:*)` → three namespaces,
  `mcp__plugin_fls_playwright__*` → `mcp__plugin_ds_playwright__*`, `.claude/fls/scripts/…`
  permission literals, and the `SessionStart` hook's `$FLS_PLUGIN` check and message wording.
- `CLAUDE.md` skeleton — check for a legacy plugin-check first line and for any `fls:`-namespaced
  command or skill references in the conventions prose.
- The manifest's own file-tree listing (line ~37) needs its `claude.sh` comment reworded, and the
  gitignored-files note (line ~72) already says `.claude/fls-dev/config.local.md` — verify whether
  `.claude/ds/` and `.claude/sdd/` config dirs should also be listed for the scaffold.

Per §1.1, the scaffold's `enabledPlugins` must read `{"ds": true, "fls-dev": true, "sdd": true}` —
manifest names, not directory names. Getting this wrong bakes a silent fault into every project
created from the template.

---

## 6. Notes for `/update_product_docs` (todo step 10)

Low yield, and worth saying so plainly. `docs/` contains **zero** references to `fls-claude-plugin`,
`claude_plugins`, or `claude.sh` (verified by grep across `docs/`, `CLAUDE.md`, `README.md`). This
change alters no user-facing product behaviour, so `docs/product/` almost certainly needs nothing.
The plugin READMEs (three new ones, written on this branch) already carry the developer-facing
documentation of the split.

The one thing to check: `docs/install.md` and `docs/how tos/` for any developer-setup instructions
that mention launching Claude or running `/fls:init`.

---

## 7. Notes for `/update_claude_plugin_fls_content` (todo step 13)

The `fls-content` plugin **moved** (`fls-content-plugin/` → `claude_plugins/fls-content/`) but its
contents are byte-identical — the diff shows pure renames with zero content change. No authoring
functionality changed, so the sync itself is likely a no-op.

Two path consequences to verify instead:

- `pyproject.toml` `testpaths` and the two ruff `per-file-ignores` entries now point at
  `claude_plugins/fls-content/…`, and the mypy `exclude` regex uses a negative lookahead
  (`claude_plugins/(?!fls-content/validate)`) to keep type-checking the validator while excluding
  the other three plugins. Confirm the validator suite still collects and type-checks.
- `spec_dd/1. next/content-plugin-distribution/idea.md` was updated by `38d3fcaf` so its planned
  `git subtree split` prefix reads `claude_plugins/fls-content`. That queued spec depends on this
  path being right.

---

## 8. Changes riding along in this PR that are not about plugin naming

Easy to miss when writing upgrade notes, because they sit outside `claude_plugins/`:

- **Browser-test directories renamed `tests/e2e/` → `tests/playwright/`** in `freedom_ls/base/`,
  `freedom_ls/panel_framework/`, and `freedom_ls/student_interface/`; plus
  `student_interface/tests/form_ui_tests.py` (7 playwright-marked tests that sat outside any browser
  dir) moved in with the rest. **The `playwright` marker itself did not change** — it already existed
  on `main` with the same name, and CI selects by marker, never by path. So the downstream-exclusion
  guarantee is untouched. A downstream project that references these paths directly (rather than by
  marker) needs the rename; one that filters `-m "not playwright"` needs nothing.
- `install_dev.sh` now delegates to `.claude/fls-dev/scripts/install_dev.sh`.
- `freedom_ls/panel_framework/tests/stub_panels.py` — one-line import path change from the test move.

---

## 9. Loose ends noticed while reviewing (not blockers, but decide before merge)

- ~~**§1.1 `enabledPlugins` key mismatch.**~~ Fixed on this branch — see §1.1.
- **14 live `todo.md` files** under `spec_dd/1. next/` and `spec_dd/2. in progress/` still carry the
  header line "See `fls-claude-plugin/commands/sdd/README.md` for the full workflow description".
  The generator (`claude_plugins/sdd/commands/protected/setup_todo_list.md`) was correctly updated to
  emit `claude_plugins/sdd/commands/README.md`, so only already-generated files are stale. This is
  prose in a checklist header — nothing reads that path programmatically — but it is a dangling
  reference in 14 active specs, including this spec's own `todo.md`. Cheap sweep; worth doing.
- Specs under `spec_dd/3. done/` and `spec_dd/0. noop/` intentionally keep the old paths as the
  historical record (per `38d3fcaf`). Leave them.
- The `fls-claude-plugin` / `.claude/fls/` strings remaining in `claude_plugins/fls-dev/README.md`
  and `claude_plugins/fls-dev/commands/init.md` are **deliberate** — they are the legacy-migration
  instructions. Not stale.
- The `sdd` plugin is not yet standalone: `setup_todo_list` and `next.md` name `/fls-dev:*` steps,
  and `fls-dev` commands spawn `sdd` agents. Documented as accepted and deferred in the `sdd`
  README's coupling note and spec §12. Upgrade notes should not imply `sdd` is independently
  installable yet.
