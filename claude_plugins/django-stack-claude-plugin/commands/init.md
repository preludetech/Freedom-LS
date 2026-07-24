---
description: Initialise the django-stack (ds) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the django-stack (ds) Plugin

Set up the `ds` Claude Code plugin for this project, and — because `ds` is the **primary init owner** —
set up the shared, multi-plugin artifacts that all of the dev plugins depend on.

## Scope

`ds:init` is **plugin-bootstrap only.** It wires the Claude Code plugins into an existing project. It
does NOT scaffold Django project structure (`config/`, `pyproject.toml`, Tailwind config, a `CLAUDE.md`
skeleton) — those come from the template repo. Run `ds:init` after the project already exists.

`ds` is the **primary init owner** for artifacts shared across `ds`, `fls-dev`, and `sdd`:

- the root **`claude.sh`** launcher (all three `--plugin-dir` flags + `$CLAUDE_PLUGINS_LOADED`),
- the **`SessionStart`** hook in `.claude/settings.json`,
- the `.claude/settings.local.json` line in **`.gitignore`**.

The `fls-dev` and `sdd` init commands detect these and skip them — `ds:init` writes them. Each of the three
inits merges only **its own** `enabledPlugins` key and permissions, and writes only its own
`.claude/<plugin>/` config dir.

## Hard requirements — do not regress

Each operation is additive or create-when-absent, with the one deliberate exception noted for `hooks`.

- **`.claude/settings.json`** — merge, don't replace. Add missing `allow`/`deny` entries, add
  `"django-stack": true` to `enabledPlugins` (only this key — never touch `fls-dev`/`sdd` keys), and
  merge the `SessionStart` hook. Never replace the whole file, and never touch `allow`/`deny`/
  `enabledPlugins` entries that already exist. **Exception:** the `hooks` section is plugin-owned — only
  `SessionStart` is permitted there (see Step 1 and validation).
- **`.claude/ds/config.md`** — create when absent, otherwise extend (add any key the default defines but
  the file lacks; preserve every existing value, comment, and ordering; never re-prompt for options the
  file already has).
- **`.gitignore`** — append missing entries only. Never remove or reorder existing lines.
- **Wrapper scripts** (`claude.sh` at the project root; the others under `.claude/ds/scripts/`) — copy
  the template, substitute `__FLS_PATH__`, and mark executable **only when the destination file does not
  yet exist**. If a script is already present, skip it (but still run the sentinel migration in Step 6).

## Step 1: Merge recommended permissions into `.claude/settings.json`

1. Read `${CLAUDE_PLUGIN_ROOT}/templates/settings.json` for the recommended `ds` permission baseline.
2. If `.claude/settings.json` exists:
   - Read and parse the existing permissions.
   - Add any missing `allow` rules (don't duplicate existing ones).
   - Add any missing `deny` rules (don't duplicate existing ones).
   - Add `"django-stack": true` to `enabledPlugins` (create the key if it doesn't exist). Do **not**
     add or remove other plugins' keys.
   - Merge the `SessionStart` hook from the template into the existing `hooks` section (create `hooks`
     if missing, add `SessionStart` if missing, append the command if an equivalent one isn't already
     there). Leave other hook events alone if another tool owns them.
   - Write the updated file.
3. If `.claude/settings.json` doesn't exist: create it from the template (it already carries
   `enabledPlugins: {"django-stack": true}` and the `SessionStart` hook).
4. Report what was added/changed.

## Step 2: Create or extend `.claude/ds/config.md`

`ds` needs little per-project config. Store the dev-site base URL the `ds:use-playwright` skill reads,
and the Alpine.js CSP-build flag the `ds:alpine-js` skill reads.

**Do not prompt the user for these values.** Write the file with the documented defaults and tell the
user where it is so they can fill it in themselves.

1. Ensure the `.claude/ds/` directory exists (create it if missing).
2. If `.claude/ds/config.md` does **not** exist, write it with the defaults:
   - the dev base URL `http://127.0.0.1:8000` under a `## Project Settings` section;
   - the Alpine.js CSP-build flag under a `## Alpine.js` section as `- CSP build: enabled`. `enabled`
     is the safe default the `ds:alpine-js` skill assumes.
   (Product-specific config — dev credentials, the template-repo path — is written by the `fls-dev`
   init into `.claude/fls-dev/config.md`, not here.)
3. If it already exists, add any missing key using the default (including the `## Alpine.js` section
   with `- CSP build: enabled` if absent), preserving every existing value and comment; never re-prompt
   for options already present.
4. Tell the user the config lives at `.claude/ds/config.md` and that they should review and edit the
   base URL and the Alpine CSP-build flag to match this project — the defaults are only a starting point.

## Step 3: Determine the FLS path (do not prompt — default and persist for the other inits)

`FLS_PATH` is the relative path from the project root to whichever checkout holds `claude_plugins/`; it
is baked into `claude.sh` and the wrapper scripts so they can locate the plugin dir at runtime. The three
inits must agree on one path; whichever runs first sets it and the others reuse it. **Do not prompt the
user for it.**

1. If a root `claude.sh` already exists, read its `FLS_PATH="…"` value and reuse it.
2. Otherwise default to `.` (the common case, where the project root itself holds `./claude_plugins/`).
3. Validate that `<fls_path>/claude_plugins/django-stack-claude-plugin/` exists. If it does not, do not
   guess — stop and tell the user to set `FLS_PATH` in `claude.sh` to the relative path of the checkout
   that holds `claude_plugins/` (e.g. `submodules/Freedom-LS`), then re-run.
4. Store this path for the wrapper-script generation below (it is baked into `claude.sh` as `FLS_PATH`,
   which is where the `fls-dev` and `sdd` inits read it back). If the default `.` is used but this project
   holds `claude_plugins/` somewhere else (e.g. a submodule), the user edits `FLS_PATH` in `claude.sh`
   afterwards — surface this in the final summary.

## Step 4: Generate the shared launcher and `ds` wrapper scripts

1. Install the root launcher: if `claude.sh` does **not** exist at the project root, copy
   `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/claude.sh`, replace `__FLS_PATH__` with the Step 3
   path, and make it executable. (If it already exists, leave it — Step 6 migrates it in place.)
2. Ensure `.claude/ds/scripts/` exists.
3. For each remaining template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/` (`find_available_port.sh`,
   `db_clear.sh`, `kill_runserver.sh`, `fetch_pr_comments.sh`): if a script of that name does not yet
   exist under `.claude/ds/scripts/`, copy it there, replace `__FLS_PATH__`, and make it executable.
   Skip any that already exist.

## Step 5: Update `.gitignore`

1. Read `.gitignore`.
2. If `.claude/ds/config.local.md` is not already listed, add it.
3. If `.claude/settings.local.json` is not already listed, add it (this line is `ds`-owned; the other
   inits skip it).

## Step 6: Sentinel migration — rewrite `$FLS_PLUGIN` → `$CLAUDE_PLUGINS_LOADED`

A plain additive merge cannot rename a sentinel already baked into an existing project. Actively detect
and rewrite it (mirroring the earlier "clean up legacy `CLAUDE.md` line" precedent). Run this even when
Step 1/Step 4 skipped an existing file.

1. **Root `claude.sh`:** if it references the old sentinel or the old single-plugin launcher line:
   - Rewrite every `FLS_PLUGIN=1` / `$FLS_PLUGIN` occurrence to `CLAUDE_PLUGINS_LOADED=1` /
     `$CLAUDE_PLUGINS_LOADED`.
   - If the launcher still has a single `--plugin-dir` flag pointing at the old pre-split monolith
     plugin directory, replace that whole invocation with the three-plugin form from
     `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/claude.sh` (`django-stack`, `fls-dev`, `sdd` —
     not `fls-content`).
2. **`.claude/settings.json`:** in the `SessionStart` hook, rewrite `$FLS_PLUGIN` → `$CLAUDE_PLUGINS_LOADED`
   and reword any "FLS PLUGIN NOT LOADED" message to the plugin-neutral wording in the template.
3. Report each rewrite made.

## Step 7: Clean up legacy CLAUDE.md plugin check

Earlier init versions prepended a `CLAUDE.md` line asking Claude to check `$FLS_PLUGIN` each session;
the `SessionStart` hook replaces it.

1. Read `CLAUDE.md` at the project root (if it exists).
2. If it starts with a line mentioning `FLS_PLUGIN`, remove that line and the blank line following it.
3. Otherwise skip.

## Step 8: Validate the setup

Run these checks and report results:

1. Confirm `django-stack` is in `enabledPlugins` in `.claude/settings.json`.
2. Confirm `claude.sh` exists at the project root, is executable, and its launch line uses
   `CLAUDE_PLUGINS_LOADED=1` with three `--plugin-dir` flags.
3. Confirm the `ds` wrapper scripts exist under `.claude/ds/scripts/` and are executable.
4. Confirm hook scripts in the plugin (`scripts/hooks/*.sh`) are executable.
5. Confirm the `SessionStart` hook in `.claude/settings.json` checks `$CLAUDE_PLUGINS_LOADED` (not
   `$FLS_PLUGIN`).
6. Confirm wrapper scripts have the resolved `FLS_PATH` (not `__FLS_PATH__`).
7. Confirm `CLAUDE.md` no longer contains the legacy `FLS_PLUGIN` line.
8. Confirm `.claude/ds/config.md` contains a `## Alpine.js` section with a `CSP build` value
   (`enabled` or `disabled`).
9. Report any issues found.

Print a summary of everything that was done. In the summary, explicitly point the user at
`.claude/ds/config.md` and tell them to fill in the base URL and Alpine CSP-build flag themselves. If the
FLS path defaulted to `.`, also tell them to edit `FLS_PATH` in `claude.sh` if this project holds
`claude_plugins/` somewhere other than the project root (e.g. a submodule).
