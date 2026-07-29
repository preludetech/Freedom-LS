---
description: Initialise the django-stack (ds) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the django-stack (ds) Plugin

Set up the `ds` Claude Code plugin for this project. `ds` is a portable Django-stack plugin — it carries
zero product-specific knowledge and depends on no other plugin. This command wires `ds` into an existing
project and creates the generic launcher/hook/gitignore artifacts a project needs to load Claude Code
plugins at all — but only when they are missing.

## Scope

`ds:init` is **plugin-bootstrap only.** It wires the `ds` plugin into an existing project. It
does NOT scaffold Django project structure (`config/`, `pyproject.toml`, Tailwind config, a `CLAUDE.md`
skeleton) — those come from the project template. Run `ds:init` after the project already exists.

`ds:init` writes only its **own** slice — the `ds` `enabledPlugins` key, `ds` permissions, the
`.claude/ds/` config dir, and the `ds` wrapper scripts. Alongside that it creates a few **generic,
plugin-neutral** artifacts a Claude Code project needs regardless of which plugins are installed, and only
when they are absent:

- the root **`claude.sh`** launcher (starting with the `django-stack` `--plugin-dir` flag +
  `$CLAUDE_PLUGINS_LOADED`),
- the **`SessionStart`** hook in `.claude/settings.json`,
- the `.claude/settings.local.json` line in **`.gitignore`**.

`claude.sh` is a shared file: `ds:init` ensures **its own** `--plugin-dir` line is present and never
touches any other `--plugin-dir` line. If additional plugins are installed, each of their inits adds its
own line the same way.

## Hard requirements — do not regress

Each operation is additive or create-when-absent, with the one deliberate exception noted for `hooks`.

- **`.claude/settings.json`** — merge, don't replace. Add missing `allow`/`deny` entries, add
  `"ds": true` to `enabledPlugins` (only this key — never touch other plugins' keys), and
  merge the `SessionStart` hook. Never replace the whole file, and never touch `allow`/`deny`/
  `enabledPlugins` entries that already exist. **Exception:** the `hooks` section is plugin-owned — only
  `SessionStart` is permitted there (see Step 1 and validation).
- **`.claude/ds/config.md`** — create when absent, otherwise extend (add any key the default defines but
  the file lacks; preserve every existing value, comment, and ordering; never re-prompt for options the
  file already has).
- **`.gitignore`** — append missing entries only. Never remove or reorder existing lines.
- **Wrapper scripts** (`claude.sh` at the project root; the others under `.claude/ds/scripts/`) — copy
  the template, substitute `__PLUGINS_ROOT__`, and mark executable **only when the destination file does
  not yet exist**. If a script is already present, skip it (but still run the sentinel migration in
  Step 6). `claude.sh` is the one shared file: when it already exists, ensure the `django-stack`
  `--plugin-dir` line is present without disturbing any other line.

## Step 1: Merge recommended permissions into `.claude/settings.json`

1. Read `${CLAUDE_PLUGIN_ROOT}/templates/settings.json` for the recommended `ds` permission baseline.
2. If `.claude/settings.json` exists:
   - Read and parse the existing permissions.
   - Add any missing `allow` rules (don't duplicate existing ones).
   - Add any missing `deny` rules (don't duplicate existing ones).
   - Add `"ds": true` to `enabledPlugins` (create the key if it doesn't exist). Do **not**
     add or remove other plugins' keys.
   - Merge the `SessionStart` hook from the template into the existing `hooks` section (create `hooks`
     if missing, add `SessionStart` if missing, append the command if an equivalent one isn't already
     there). Leave other hook events alone if another tool owns them.
   - Write the updated file.
3. If `.claude/settings.json` doesn't exist: create it from the template (it already carries
   `enabledPlugins: {"ds": true}` and the `SessionStart` hook).
4. Report what was added/changed.

## Step 2: Create or extend `.claude/ds/config.md`

`ds` needs little per-project config. Store the dev-site base URL the `ds:use-playwright` skill reads,
the Alpine.js CSP-build flag the `ds:alpine-js` skill reads, and the admin flags the
`ds:admin-interface` skill reads.

**Do not prompt the user for these values.** Write the file with the documented defaults and tell the
user where it is so they can fill it in themselves.

1. Ensure the `.claude/ds/` directory exists (create it if missing).
2. If `.claude/ds/config.md` does **not** exist, write it with the defaults:
   - the dev base URL `http://127.0.0.1:8000` under a `## Project Settings` section;
   - the Alpine.js CSP-build flag under a `## Alpine.js` section as `- CSP build: enabled`. `enabled`
     is the safe default the `ds:alpine-js` skill assumes.
   - the admin flags under an `## Admin` section as `- Admin theme: standard` and
     `- Object permissions (django-guardian): disabled`. These portable defaults keep `ds` on plain
     Django admin with no extra dependencies; the `ds:admin-interface` skill reads them.
3. If it already exists, add any missing key using the default (including the `## Alpine.js` section
   with `- CSP build: enabled`, and the `## Admin` section with the two admin flags, if absent),
   preserving every existing value and comment; never re-prompt for options already present.
4. Tell the user the config lives at `.claude/ds/config.md` and that they should review and edit the
   base URL, the Alpine CSP-build flag, and the admin flags to match this project — the defaults are
   only a starting point.

## Step 3: Determine `PLUGINS_ROOT` (do not prompt)

`PLUGINS_ROOT` is the relative path from the project root to whichever checkout holds `claude_plugins/`;
it is baked into `claude.sh` and the wrapper scripts so they can locate the plugin dir at runtime.
**Do not prompt the user for it.**

1. If a root `claude.sh` already exists, read its `PLUGINS_ROOT="…"` value and reuse it.
2. Otherwise default to `.` (the common case, where the project root itself holds `./claude_plugins/`).
3. Validate that `<PLUGINS_ROOT>/claude_plugins/django-stack/` exists. If it does not, do
   not guess — stop and tell the user to set `PLUGINS_ROOT` in `claude.sh` to the relative path of the
   checkout that holds `claude_plugins/`, then re-run.
4. Store this path for the wrapper-script generation below (it is baked into `claude.sh` as
   `PLUGINS_ROOT`). If the default `.` is used but this project holds `claude_plugins/` somewhere else
   (e.g. a submodule), the user edits `PLUGINS_ROOT` in `claude.sh` afterwards — surface this in the
   final summary.

## Step 4: Generate the launcher and `ds` wrapper scripts

1. Install the root launcher:
   - If `claude.sh` does **not** exist at the project root, copy
     `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/claude.sh`, replace `__PLUGINS_ROOT__` with the
     Step 3 path, and make it executable.
   - If it already exists, leave the file in place but ensure the `django-stack` `--plugin-dir` line is
     present: if no line pointing at `claude_plugins/django-stack` is found, insert one
     (matching the template's form, with the resolved `PLUGINS_ROOT`) immediately above the `"$@"` line.
     Do not touch any other `--plugin-dir` line. (Step 6 also migrates an existing launcher in place.)
2. Ensure `.claude/ds/scripts/` exists.
3. For each remaining template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/` (`find_available_port.sh`,
   `db_clear.sh`, `kill_runserver.sh`, `fetch_pr_comments.sh`): if a script of that name does not yet
   exist under `.claude/ds/scripts/`, copy it there, replace `__PLUGINS_ROOT__`, and make it executable.
   Skip any that already exist.

## Step 5: Update `.gitignore`

1. Read `.gitignore`.
2. If `.claude/ds/config.local.md` is not already listed, add it.
3. If `.claude/settings.local.json` is not already listed, add it.

## Step 6: Sentinel, variable, and header migration in existing artifacts

A plain additive merge cannot rename a sentinel or variable already baked into an existing project.
Actively detect and rewrite them (mirroring the "clean up legacy `CLAUDE.md` line" precedent in Step 7).
Run this even when Step 1/Step 4 skipped an existing file.

1. **Root `claude.sh`:** if it references an old sentinel or variable name, or predates the
   `PLUGINS_ROOT` form:
   - Rewrite every `FLS_PLUGIN=1` / `$FLS_PLUGIN` occurrence to `CLAUDE_PLUGINS_LOADED=1` /
     `$CLAUDE_PLUGINS_LOADED`.
   - Rewrite every `FLS_PATH=` / `$FLS_PATH` occurrence to `PLUGINS_ROOT=` / `$PLUGINS_ROOT`.
   - If there is no `PLUGINS_ROOT="…"` assignment at all, insert one carrying the Step 3 value
     immediately above the `SCRIPT_DIR=` line, then rewrite any `--plugin-dir` path of the form
     `"$SCRIPT_DIR/claude_plugins/…"` to `"$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/…"`. Only touch
     `--plugin-dir` lines that lack the variable — a line another plugin's init already wrote in the
     `$PLUGINS_ROOT` form is correct, leave it.
   - If the launcher still has a `--plugin-dir` flag pointing at a pre-split monolith plugin directory,
     replace **that one line** with the `django-stack` `--plugin-dir` line from
     `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/claude.sh` (with the resolved `PLUGINS_ROOT`).
     Leave every other `--plugin-dir` line alone — other installed plugins own theirs.
2. **`.claude/ds/scripts/*.sh`:** rewrite each existing wrapper script in place — never regenerate it,
   and never touch anything below `# === Project-specific setup ===`:
   - every `FLS_PATH=` / `$FLS_PATH` occurrence → `PLUGINS_ROOT=` / `$PLUGINS_ROOT`;
   - a pre-split header line (`# <name>.sh — Generated by fls plugin init`, or any other wording that
     does not name this plugin) → `# <name>.sh — Generated by the django-stack (ds) plugin init`;
   - the two-line comment block explaining the path variable — an older init wrote
     ``# FLS_PATH is set during `…:init` to the path where FLS is installed`` followed by a
     `# (e.g., "submodules/Freedom-LS" …)` line — → the plugin-neutral wording carried by
     `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/db_clear.sh`:

     ```bash
     # PLUGINS_ROOT is set during `ds:init` to the relative path from the project root
     # to the checkout that holds `claude_plugins/` (default "." — the project root itself).
     ```

   - any remaining `__PLUGINS_ROOT__` placeholder → the Step 3 `PLUGINS_ROOT` value.

   Match the prose block on its own, not via the header line: a partially-migrated script can have a
   correct header and a stale block, and a header-only rule would silently skip exactly those files.
   `ds` carries no product-specific domain knowledge, so no artifact it generates may name a product.

   Scope this to `.claude/ds/scripts/` only. Other plugins own their own script directories and
   migrate them in their own inits.
3. **`.claude/settings.json`:** in the `SessionStart` hook, rewrite `$FLS_PLUGIN` → `$CLAUDE_PLUGINS_LOADED`
   and reword any "FLS PLUGIN NOT LOADED" message to the plugin-neutral wording in the template.
4. Report each rewrite made.

## Step 7: Clean up legacy CLAUDE.md plugin check

Earlier init versions prepended a `CLAUDE.md` line asking Claude to check a plugin-loaded sentinel each
session; the `SessionStart` hook replaces it.

1. Read `CLAUDE.md` at the project root (if it exists).
2. If it starts with a line mentioning `FLS_PLUGIN` or `CLAUDE_PLUGINS_LOADED`, remove that line and the
   blank line following it.
3. Otherwise skip.

## Step 8: Validate the setup

Run these checks and report results:

1. Confirm `ds` is in `enabledPlugins` in `.claude/settings.json`.
2. Confirm `claude.sh` exists at the project root, is executable, uses `CLAUDE_PLUGINS_LOADED=1`, and has
   the `django-stack` `--plugin-dir` line.
3. Confirm the `ds` wrapper scripts exist under `.claude/ds/scripts/` and are executable.
4. Confirm hook scripts in the plugin (`scripts/hooks/*.sh`) are executable.
5. Confirm the `SessionStart` hook in `.claude/settings.json` checks `$CLAUDE_PLUGINS_LOADED`.
6. Confirm every wrapper script under `.claude/ds/scripts/` declares `PLUGINS_ROOT` with the resolved
   value — no `__PLUGINS_ROOT__` placeholder and no `FLS_PATH` left — and that its header comments name
   the `django-stack (ds)` plugin and `ds:init`, with no product-specific terms anywhere in the file.
7. Confirm `CLAUDE.md` no longer contains a legacy plugin-check line.
8. Confirm `.claude/ds/config.md` contains a `## Alpine.js` section with a `CSP build` value
   (`enabled` or `disabled`).
9. Confirm `.claude/ds/config.md` contains an `## Admin` section with both an `Admin theme` value
   (`standard` or `unfold`) and an `Object permissions (django-guardian)` value (`enabled` or
   `disabled`).
10. Report any issues found.

Print a summary of everything that was done. In the summary, explicitly point the user at
`.claude/ds/config.md` and tell them to fill in the base URL, the Alpine CSP-build flag, and the two
admin flags themselves — the defaults assume plain Django admin with no django-guardian, which is wrong
for any project already using django-unfold or object permissions. If the plugins root defaulted to `.`,
also tell them to edit `PLUGINS_ROOT` in `claude.sh` if this project holds `claude_plugins/` somewhere
other than the project root (e.g. a submodule).
