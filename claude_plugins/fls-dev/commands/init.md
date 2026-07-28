---
description: Initialise the fls-dev plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the fls-dev Plugin

Set up the `fls-dev` Claude Code plugin for this project.

## Scope

`/fls-dev:init` is **plugin-bootstrap only.** It wires the `fls-dev` plugin into an existing project. It does NOT scaffold Django project structure — `config/`, `pyproject.toml`, Tailwind config, a `CLAUDE.md` skeleton, or a `.claude/settings.json` from scratch. Those come from the template repo. Run `/fls-dev:init` after the project already exists.

`/fls-dev:init` owns **only the `fls-dev` slice** of project setup: its `enabledPlugins` key, its own permissions, its `.claude/fls-dev/` config dir, and its own dev/DB wrapper scripts. Into the shared project-root `claude.sh` launcher it adds **only its own** `--plugin-dir` line for `fls-dev` (see Step 7); it never touches another plugin's line. The generic, plugin-neutral artifacts a Claude Code project needs — the `claude.sh` skeleton itself, the `SessionStart` hook, and the `.claude/settings.local.json` line in `.gitignore` — are created by `/ds:init`. This command **detects and reports** whether those exist and, if `claude.sh` is missing, tells the user to run `/ds:init` first.

## Hard requirements — do not regress

These behaviours must be preserved in every future edit to this command. Each operation is additive or create-when-absent.

- **`.claude/settings.json`** — merge, don't replace. Add missing `fls-dev`-owned `allow`/`deny` entries, add `"fls-dev": true` to `enabledPlugins`. Never replace the whole file, never touch `allow`/`deny`/`enabledPlugins` entries that already exist, and never touch the `hooks` section (the `SessionStart` hook is `ds`-owned — leave it alone).
- **`.claude/fls-dev/config.md` and `.claude/fls-dev/config.local.md`** — create when absent, otherwise extend. If a file already exists, add any configuration option the template defines but the file lacks (new sections/keys), using the template's default. Preserve every existing value, comment, and ordering. Never overwrite or delete existing config, and never re-prompt the user for options the file already has.
- **`.gitignore`** — append only the `fls-dev`-owned line (`.claude/fls-dev/config.local.md`). Never remove or reorder existing lines, and leave the `ds`-owned `.claude/settings.local.json` line to `/ds:init`.
- **Wrapper scripts** (the `fls-dev` dev/DB scripts under `.claude/fls-dev/scripts/`) — copy the template, substitute `__PLUGINS_ROOT__`, and mark executable **only when the destination file does not yet exist**. If a script is already present, skip it without modification. The project-root `claude.sh` skeleton is created by `/ds:init`; this command only ensures its own `--plugin-dir` line inside it (Step 7).

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

**Do not prompt the user for these values.** The template already carries sensible dev defaults; write it
verbatim and tell the user where it is so they can fill it in themselves.

1. Ensure the `.claude/fls-dev/` directory exists (create it if missing — it should already exist if Step 1 migrated a legacy dir).
2. If `.claude/fls-dev/config.md` does **not** exist, create it by copying `${CLAUDE_PLUGIN_ROOT}/templates/fls.md`
   verbatim. It ships with the defaults dev admin email `demodev@email.com`, dev admin password
   `demodev@email.com`, and base URL `http://127.0.0.1:8000`. Then tell the user the config lives at
   `.claude/fls-dev/config.md` and that they should review and edit the dev credentials and base URL to
   match this project — the defaults are only a starting point.
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

## Step 6: Determine `PLUGINS_ROOT` (do not prompt)

`PLUGINS_ROOT` is the relative path from the project root to whichever checkout holds `claude_plugins/`;
it is baked into the wrapper scripts so they can locate the plugin dir at runtime. **Do not prompt the
user for it.**

1. If a root `claude.sh` already exists (created by `/ds:init`), read its `PLUGINS_ROOT="…"` value and
   reuse it.
2. Otherwise default to `.` (the common case, where the project root itself holds `./claude_plugins/`).
   For concrete implementations the checkout is typically at `submodules/Freedom-LS`.
3. Validate that `<PLUGINS_ROOT>/claude_plugins/fls-dev/` exists. If it does not, do not
   guess — stop and tell the user to run `/ds:init` (which creates `claude.sh`) or set `PLUGINS_ROOT`
   there to the relative path of the checkout that holds `claude_plugins/`, then re-run.
4. Store this path for use in wrapper script generation and the launcher line below.

## Step 7: Generate the `fls-dev` wrapper scripts and add the launcher line

### 7a. Wrapper scripts

The `fls-dev` dev/DB wrapper scripts install under `.claude/fls-dev/scripts/` (create this directory if missing).

For each wrapper script template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/`:
1. Set the destination to `.claude/fls-dev/scripts/`.
2. Check if a script with that name already exists at the destination.
3. If it exists, **skip it** (never overwrite existing scripts).
4. If it doesn't exist, copy the template to the destination, replace `__PLUGINS_ROOT__` with the path from Step 6, and make it executable.

### 7b. Ensure the `fls-dev` `--plugin-dir` line in `claude.sh`

The project-root `claude.sh` is a shared file. `fls-dev:init` adds **only its own** line and never touches another plugin's `--plugin-dir` line.

1. If `claude.sh` does **not** exist at the project root, do not create it here — the skeleton is `ds`-owned. Tell the user to run `/ds:init` first, then re-run `/fls-dev:init`.
2. If `claude.sh` exists, look for a `--plugin-dir` line pointing at `claude_plugins/fls-dev`. If it is absent, insert one immediately above the `"$@"` line, matching the form of the existing `--plugin-dir` lines and using the Step 6 `PLUGINS_ROOT` value:

   ```bash
     --plugin-dir "$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/fls-dev" \
   ```

3. If the line is already present, leave it — never duplicate it.

## Step 8: Generic shared-artifact check (detect and defer to `/ds:init`)

The generic, plugin-neutral artifacts are created by `/ds:init`. Do **not** create or rewrite them here — detect their state and report so the user knows whether to run `/ds:init`:

1. Confirm `.claude/settings.json` has a `SessionStart` hook checking `$CLAUDE_PLUGINS_LOADED`. If it still checks a legacy sentinel or is missing, note that `/ds:init` creates and migrates it.
2. Confirm `.claude/settings.local.json` is listed in `.gitignore`. If not, note that `/ds:init` adds it.

## Step 9: Validate the setup

Run these checks and report results:

1. Confirm `fls-dev` is in `enabledPlugins` in `.claude/settings.json`.
2. Confirm `.claude/fls-dev/config.md` exists and contains required fields (email, password, base URL).
3. Confirm the `fls-dev` wrapper scripts exist under `.claude/fls-dev/scripts/` and are executable.
4. Confirm no `.claude/fls/` config dir remains (the legacy dir was migrated in Step 1).
5. Confirm `.claude/settings.json` contains the `fls-dev` `allow` entries (`Skill(fls-dev:*)`, `Bash(.claude/fls-dev/scripts/*.sh:*)`) and no lingering `Bash(.claude/fls/scripts/*.sh:*)` entry.
6. Confirm wrapper scripts have the resolved `PLUGINS_ROOT` (not `__PLUGINS_ROOT__`).
7. Confirm `claude.sh` contains the `fls-dev` `--plugin-dir` line (or that the user was told to run `/ds:init` first because `claude.sh` is missing).
8. Report any issues found, including any generic shared artifact flagged in Step 8.

Print a summary of everything that was done. In the summary, explicitly point the user at
`.claude/fls-dev/config.md` and tell them to fill in the dev credentials and base URL themselves, and at
`.claude/fls-dev/config.local.md` for the optional template-repo path.
