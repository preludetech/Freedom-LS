---
description: Initialise the spec-driven-development (sdd) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the sdd Plugin

Set up the `sdd` Claude Code plugin for this project. `sdd` provides the portable spec-driven-development
workflow (worker/mechanic agents, workflow commands, authoring skills). It needs very little per-project
config beyond the shared bits that `ds:init` already owns.

## Scope

`sdd:init` is **plugin-bootstrap only.** It wires the `sdd` plugin into an existing project. It merges
only **its own** `enabledPlugins` key and permissions and writes only its own `.claude/sdd/` config dir.

`sdd` is **not** the primary init owner. The shared, multi-plugin artifacts are owned by `ds:init` and
this command **detects and skips** them:

- the root **`claude.sh`** launcher (all three `--plugin-dir` flags + `$CLAUDE_PLUGINS_LOADED`),
- the **`SessionStart`** hook in `.claude/settings.json`,
- the `.claude/settings.local.json` line in **`.gitignore`**.

If `claude.sh` or the `SessionStart` hook is missing, do **not** create them here — tell the user to run
`/ds:init` (the primary init) and continue with the `sdd`-only steps.

## Hard requirements — do not regress

Each operation is additive or create-when-absent.

- **`.claude/settings.json`** — merge, don't replace. Add the `sdd` permission (`Skill(sdd:*)`) if
  missing and add `"sdd": true` to `enabledPlugins` (only this key — never touch `django-stack`/`fls-dev`
  keys, and never touch the `hooks` section — the `SessionStart` hook is `ds`-owned).
- **`.claude/sdd/config.md`** — create when absent, otherwise extend (add any key the default defines
  but the file lacks; preserve every existing value, comment, and ordering; never re-prompt for options
  the file already has).
- **`.gitignore`** — append missing entries only (its own `.claude/sdd/config.local.md` line). Never
  remove or reorder existing lines, and never touch the `ds`-owned `.claude/settings.local.json` line.

## Step 1: Merge the `sdd` permission and enabledPlugins key into `.claude/settings.json`

1. If `.claude/settings.json` exists:
   - Read and parse it.
   - Add `"Skill(sdd:*)"` to `permissions.allow` if it isn't already present (don't duplicate).
   - Add `"sdd": true` to `enabledPlugins` (create the key if it doesn't exist). Do **not** add or
     remove other plugins' keys.
   - **Do not touch the `hooks` section** — the `SessionStart` hook is owned by `ds:init`.
   - Write the updated file.
2. If `.claude/settings.json` does **not** exist: the base file is `ds`-owned. Tell the user to run
   `/ds:init` first (it creates the file with the `SessionStart` hook and the launcher). Do not create a
   full settings file here.
3. Report what was added/changed.

## Step 2: Create or extend `.claude/sdd/config.md`

`sdd` needs little per-project config. The one thing it *does* read at runtime is the **Worktree Scripts**
section: the worktree helpers (`protected/start_worktree.md`, `finish_worktree.md`) look here for the
per-worktree setup/teardown scripts to run. Everything else in this dir exists for parity with the other
plugins and to hold any future workflow settings.

1. Ensure the `.claude/sdd/` directory exists (create it if missing).
2. If `.claude/sdd/config.md` does **not** exist, write it with:
   - a short note that the `sdd` workflow is enabled for this project and that product-specific SDD steps
     and dev credentials live in `.claude/fls-dev/` (written by `/fls-dev:init`), not here;
   - a `## Worktree Scripts` section. Prompt the user for a **Setup script** path (run when a worktree is
     created — dependency install, per-branch dev DB, migrations, seed data) and a **Teardown script**
     path (run when a worktree is finished — e.g. dropping the per-branch dev DB). Both paths are relative
     to the project root and each **defaults to blank** (= "this project has no such step"). Use the
     canonical shape below so the reader helpers can find the values:

     ```markdown
     # SDD Plugin Configuration

     The spec-driven-development (sdd) workflow is enabled for this project. Product-specific SDD steps
     and dev credentials live in `.claude/fls-dev/` (written by `/fls-dev:init`), not here.

     ## Worktree Scripts

     Paths are relative to the project root. Leave a value blank if this project has no such step.

     - Setup script: <path or blank>
     - Teardown script: <path or blank>
     ```
3. If it already exists, add the `## Worktree Scripts` section and either key (`Setup script`,
   `Teardown script`) only if missing, using the blank default. Preserve every existing value, comment,
   and ordering; never re-prompt for options already present.

## Step 3: Determine the FLS path (reuse the shared value; do not re-prompt if already set)

`claude_plugins/` lives under the FLS checkout. The three inits agree on one path; whichever runs first
asks and the others reuse it.

1. If a root `claude.sh` already exists, read its `FLS_PATH="…"` value and reuse it (do not re-prompt).
2. Otherwise, ask the user for the relative path from the project root to the FLS checkout (e.g.
   `submodules/Freedom-LS`; default `.` for FLS itself, where the plugins live at `./claude_plugins/`).
   Note that `/ds:init` will bake this into `claude.sh`.
3. Validate that `<fls_path>/claude_plugins/sdd-claude-plugin/` exists — this confirms the `sdd` plugin
   path. If it doesn't, stop and report the bad path.

## Step 4: Update `.gitignore`

1. Read `.gitignore`.
2. If `.claude/sdd/config.local.md` is not already listed, add it.
3. Do **not** add the `.claude/settings.local.json` line — that line is `ds`-owned; `ds:init` writes it.

## Step 5: Confirm the `ds`-owned shared artifacts (detect-and-skip)

Do not write these — only check them and warn if they're missing so the user knows to run `/ds:init`.

1. Confirm a root `claude.sh` exists and its launch line uses `CLAUDE_PLUGINS_LOADED=1` with a
   `--plugin-dir` flag for `claude_plugins/sdd-claude-plugin`. If not, tell the user to run `/ds:init`.
2. Confirm `.claude/settings.json` has a `SessionStart` hook checking `$CLAUDE_PLUGINS_LOADED`. If not,
   tell the user to run `/ds:init`. Do not add the hook here.

## Step 6: Validate the setup

Run these checks and report results:

1. Confirm `sdd` is in `enabledPlugins` in `.claude/settings.json`.
2. Confirm `Skill(sdd:*)` is in `permissions.allow`.
3. Confirm `.claude/sdd/config.md` exists and contains a `## Worktree Scripts` section with both the
   `Setup script` and `Teardown script` keys (blank values are valid).
4. Confirm `.claude/sdd/config.local.md` is listed in `.gitignore`.
5. Confirm `<fls_path>/claude_plugins/sdd-claude-plugin/` exists.
6. Confirm the `ds`-owned shared artifacts (root `claude.sh`, the `SessionStart` hook) are present — and
   if not, that the user has been told to run `/ds:init`.
7. Report any issues found.

Print a summary of everything that was done.
