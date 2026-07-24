---
description: Initialise the fls-dev plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the fls-dev Plugin

Set up the `fls-dev` Claude Code plugin for this project.

## Scope

`/fls-dev:init` is **plugin-bootstrap only.** It wires the `fls-dev` plugin into an existing project. It does NOT scaffold Django project structure — `config/`, `pyproject.toml`, Tailwind config, a `CLAUDE.md` skeleton, or a `.claude/settings.json` from scratch. Those come from the template repo. Run `/fls-dev:init` after the project already exists.

`/fls-dev:init` owns **only the `fls-dev` slice** of project setup: its `enabledPlugins` key, its own permissions, its `.claude/fls-dev/` config dir, and its own dev/DB wrapper scripts. The genuinely shared, multi-plugin artifacts — the project-root `claude.sh` launcher, the `SessionStart` hook, the `$CLAUDE_PLUGINS_LOADED` sentinel migration, and the `.claude/settings.local.json` line in `.gitignore` — are owned by the **`ds` primary init** (`/ds:init`). This command **detects and skips** them so the two inits do not fight over the same lines. Run `/ds:init` to set those up.

## Hard requirements — do not regress

These behaviours must be preserved in every future edit to this command. Each operation is additive or create-when-absent.

- **`.claude/settings.json`** — merge, don't replace. Add missing `fls-dev`-owned `allow`/`deny` entries, add `"fls-dev": true` to `enabledPlugins`. Never replace the whole file, never touch `allow`/`deny`/`enabledPlugins` entries that already exist, and never touch the `hooks` section (the `SessionStart` hook is `ds`-owned — leave it alone).
- **`.claude/fls-dev/config.md` and `.claude/fls-dev/config.local.md`** — create when absent, otherwise extend. If a file already exists, add any configuration option the template defines but the file lacks (new sections/keys), using the template's default. Preserve every existing value, comment, and ordering. Never overwrite or delete existing config, and never re-prompt the user for options the file already has.
- **`.gitignore`** — append only the `fls-dev`-owned line (`.claude/fls-dev/config.local.md`). Never remove or reorder existing lines, and leave the `ds`-owned `.claude/settings.local.json` line to `/ds:init`.
- **Wrapper scripts** (the `fls-dev` dev/DB scripts under `.claude/fls-dev/scripts/`) — copy the template, substitute `__FLS_PATH__`, and mark executable **only when the destination file does not yet exist**. If a script is already present, skip it without modification. The project-root `claude.sh` launcher is `ds`-owned — do not generate it here.

## Step 1: Migrate any legacy `.claude/fls/` config dir to `.claude/fls-dev/`

The product plugin was renamed `fls` → `fls-dev`, so a project set up by an older `/fls:init` will have a `.claude/fls/` config dir and `Bash(.claude/fls/scripts/*.sh:*)` permission entries. A plain additive merge cannot move an existing directory, so migrate explicitly **before** writing any new config:

1. If `.claude/fls/` exists and `.claude/fls-dev/` does not, rename the directory: `git mv .claude/fls .claude/fls-dev` (fall back to a plain `mv` if the dir is untracked). This carries the existing `config.md`, `config.local.md`, and `scripts/` across intact.
2. If both `.claude/fls/` and `.claude/fls-dev/` exist, merge the legacy dir's contents into `.claude/fls-dev/` (preserving existing `.claude/fls-dev/` values) and remove the emptied `.claude/fls/`.
3. In `.claude/settings.json`, rewrite any live `Bash(.claude/fls/scripts/*.sh:*)` permission entry to `Bash(.claude/fls-dev/scripts/*.sh:*)` (and any other `.claude/fls/scripts/…` permission literal to `.claude/fls-dev/scripts/…`). This is an in-place rewrite of an already-baked name, not an additive merge.
4. Report what was migrated.

## Step 2: Merge `fls-dev` permissions and enabledPlugins into `.claude/settings.json`

1. If `.claude/settings.json` exists:
   - Read it and parse the existing permissions.
   - Add these `fls-dev`-owned `allow` entries if missing (don't duplicate existing ones):
     - `Skill(fls-dev:*)`
     - `Bash(.claude/fls-dev/scripts/*.sh:*)`
   - Add `"fls-dev": true` to `enabledPlugins` (create the key if it doesn't exist).
   - **Do not** add or modify the `SessionStart` hook, the `$CLAUDE_PLUGINS_LOADED` sentinel, or any other `hooks` entry — those are `ds`-owned. If they are missing, note it and direct the user to run `/ds:init`.
   - Write the updated file.
2. If `.claude/settings.json` doesn't exist:
   - Create a minimal file with `enabledPlugins: {"fls-dev": true}` and the two `fls-dev` `allow` entries above. Do **not** author the shared hook/permission baseline — direct the user to run `/ds:init` for the shared setup.
3. Report what was added/changed.

## Step 3: Create or extend `.claude/fls-dev/config.md`

1. Ensure the `.claude/fls-dev/` directory exists (create it if missing — it should already exist if Step 1 migrated a legacy dir).
2. If `.claude/fls-dev/config.md` does **not** exist:
   - Ask the user for:
     - Dev admin email (default: `demodev@email.com`)
     - Dev admin password (default: `demodev@email.com`)
     - Base URL (default: `http://127.0.0.1:8000`)
   - Generate `.claude/fls-dev/config.md` from `${CLAUDE_PLUGIN_ROOT}/templates/fls.md`, substituting the user's values.
3. If `.claude/fls-dev/config.md` already exists, extend it instead of skipping:
   - Compare it against `${CLAUDE_PLUGIN_ROOT}/templates/fls.md`.
   - Add any section or key the template defines but the existing file lacks, using the template's default value — do **not** re-prompt the user for options the file already carries.
   - Preserve every existing value, comment, and ordering — never overwrite or delete what's already there.
   - If the file already has every option the template defines, leave it untouched.

## Step 4: Create or extend `.claude/fls-dev/config.local.md`

1. If `.claude/fls-dev/config.local.md` does **not** exist, copy it from `${CLAUDE_PLUGIN_ROOT}/templates/fls.local.md`.
2. If it already exists, extend it instead of skipping:
   - Compare it against `${CLAUDE_PLUGIN_ROOT}/templates/fls.local.md`.
   - Add any section or key the template defines but the existing file lacks, using the template's default/placeholder.
   - Preserve every existing value and comment — never overwrite or delete what's already there.
   - If the file already has every option the template defines, leave it untouched.

This file carries machine-specific overrides, including the `## Template Repo` section where the user records the absolute path to their local clone of the concrete-project template repo. The `/update_template_repo` step reads that path; leave it blank if the user doesn't maintain the template repo locally.

## Step 5: Update `.gitignore`

1. Read `.gitignore`.
2. If `.claude/fls-dev/config.local.md` is not already listed, add it.
3. Leave the shared `.claude/settings.local.json` line to `/ds:init` — do not add or remove it here.

## Step 6: Determine FLS path

1. Ask the user for the relative path from the project root to FLS (e.g., `submodules/Freedom-LS`).
   - Default: `.` (for FLS itself, where the plugin is at `./claude_plugins/fls-dev-claude-plugin/`).
   - For concrete implementations, this is typically `submodules/Freedom-LS`.
2. Validate that `<fls_path>/claude_plugins/fls-dev-claude-plugin/` exists.
3. Store this path for use in wrapper script generation. (If `/ds:init` already asked for and persisted this path, reuse it rather than re-prompting.)

## Step 7: Generate the `fls-dev` wrapper scripts

The `fls-dev` dev/DB wrapper scripts install under `.claude/fls-dev/scripts/` (create this directory if missing). The project-root `claude.sh` launcher is **`ds`-owned** — do not generate it here.

For each wrapper script template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/`:
1. Set the destination to `.claude/fls-dev/scripts/`.
2. Check if a script with that name already exists at the destination.
3. If it exists, **skip it** (never overwrite existing scripts).
4. If it doesn't exist, copy the template to the destination, replace `__FLS_PATH__` with the path from Step 6, and make it executable.

## Step 8: Shared-artifact check (detect and defer to `/ds:init`)

Do **not** create or rewrite these here — they are `ds`-owned. Detect their state and report so the user knows whether to run `/ds:init`:

1. Confirm the project-root `claude.sh` launcher exists and passes `--plugin-dir` for `fls-dev`. If it is missing or does not load `fls-dev`, note that `/ds:init` must be run.
2. Confirm `.claude/settings.json` has a `SessionStart` hook checking `$CLAUDE_PLUGINS_LOADED`. If it still checks the legacy `$FLS_PLUGIN`, note that `/ds:init` performs the sentinel migration.
3. Confirm `.claude/settings.local.json` is listed in `.gitignore`. If not, note that `/ds:init` adds it.

## Step 9: Validate the setup

Run these checks and report results:

1. Confirm `fls-dev` is in `enabledPlugins` in `.claude/settings.json`.
2. Confirm `.claude/fls-dev/config.md` exists and contains required fields (email, password, base URL).
3. Confirm the `fls-dev` wrapper scripts exist under `.claude/fls-dev/scripts/` and are executable.
4. Confirm no `.claude/fls/` config dir remains (the legacy dir was migrated in Step 1).
5. Confirm `.claude/settings.json` contains the `fls-dev` `allow` entries (`Skill(fls-dev:*)`, `Bash(.claude/fls-dev/scripts/*.sh:*)`) and no lingering `Bash(.claude/fls/scripts/*.sh:*)` entry.
6. Confirm wrapper scripts have the correct `FLS_PATH` (not `__FLS_PATH__`).
7. Report any issues found, including any `ds`-owned shared artifact flagged in Step 8.

Print a summary of everything that was done.
