---
description: Initialise the spec-driven-development (sdd) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the sdd Plugin

Set up the `sdd` Claude Code plugin for this project. `sdd` provides the portable spec-driven-development
workflow (worker/mechanic agents, workflow commands, authoring skills). It needs very little per-project
config beyond the generic shared bits that `ds:init` creates.

## Scope

`sdd:init` is **plugin-bootstrap only.** It wires the `sdd` plugin into an existing project. It merges
only **its own** `enabledPlugins` key and permissions and writes only its own `.claude/sdd/` config dir.
Into the shared project-root `claude.sh` launcher it adds **only its own** `--plugin-dir` line for `sdd`
(see Step 5); it never touches another plugin's line.

The generic, plugin-neutral artifacts are created by `ds:init` and this command **detects and reports**
them:

- the root **`claude.sh`** skeleton (with `$CLAUDE_PLUGINS_LOADED`),
- the **`SessionStart`** hook in `.claude/settings.json`,
- the `.claude/settings.local.json` line in **`.gitignore`**.

If `claude.sh` is missing, do **not** create it here — tell the user to run `/ds:init` first, then re-run
`/sdd:init` so its `--plugin-dir` line can be added.

## Hard requirements — do not regress

Each operation is additive or create-when-absent.

- **`.claude/settings.json`** — merge, don't replace. Add the `sdd` permission (`Skill(sdd:*)`) if
  missing and add `"sdd": true` to `enabledPlugins` (only this key — never touch `ds`/`fls-dev`
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

**Do not prompt the user for these values.** Write the file with blank defaults and tell the user where it
is so they can fill it in themselves.

1. Ensure the `.claude/sdd/` directory exists (create it if missing).
2. If `.claude/sdd/config.md` does **not** exist, write it with:
   - a short note that the `sdd` workflow is enabled for this project and that product-specific SDD steps
     and dev credentials live in `.claude/fls-dev/` (written by `/fls-dev:init`), not here;
   - a `## Worktree Scripts` section carrying a **Setup script** path (run when a worktree is created —
     dependency install, per-branch dev DB, migrations, seed data) and a **Teardown script** path (run
     when a worktree is finished — e.g. dropping the per-branch dev DB). Both paths are relative to the
     project root and each is written **blank** by default (= "this project has no such step"); the user
     fills them in afterwards. Use the canonical shape below so the reader helpers can find the values:

     ```markdown
     # SDD Plugin Configuration

     The spec-driven-development (sdd) workflow is enabled for this project. Product-specific SDD steps
     and dev credentials live in `.claude/fls-dev/` (written by `/fls-dev:init`), not here.

     ## Worktree Scripts

     Paths are relative to the project root. Leave a value blank if this project has no such step.

     - Setup script:
     - Teardown script:
     ```

   After writing, tell the user the config lives at `.claude/sdd/config.md` and that they should fill in
   the Setup and Teardown script paths themselves (leaving either blank if this project has no such step).
3. If it already exists, add the `## Worktree Scripts` section and either key (`Setup script`,
   `Teardown script`) only if missing, using the blank default. Preserve every existing value, comment,
   and ordering; never re-prompt for options already present.

## Step 3: Determine `PLUGINS_ROOT` (do not prompt — reuse the shared value or default)

`PLUGINS_ROOT` is the relative path from the project root to whichever checkout holds `claude_plugins/`.
Every init reads the same value from `claude.sh`; whichever runs first bakes it in and the others reuse
it. **Do not prompt the user for it.**

1. If a root `claude.sh` already exists, read its `PLUGINS_ROOT="…"` value and reuse it.
2. Otherwise default to `.` (the common case, where the project root itself holds `./claude_plugins/`).
   `/ds:init` bakes this into `claude.sh`.
3. Validate that `<PLUGINS_ROOT>/claude_plugins/sdd/` exists — this confirms the `sdd`
   plugin path. If it doesn't, stop and tell the user to run `/ds:init` (which creates `claude.sh`) or set
   `PLUGINS_ROOT` there to the relative path of the checkout that holds `claude_plugins/`, then re-run.

## Step 4: Update `.gitignore`

1. Read `.gitignore`.
2. If `.claude/sdd/config.local.md` is not already listed, add it.
3. Do **not** add the `.claude/settings.local.json` line — that line is `ds`-owned; `ds:init` writes it.

## Step 5: Ensure the `sdd` `--plugin-dir` line, and check the generic artifacts

### 5a. Add the `sdd` launcher line

The project-root `claude.sh` is a shared file. `sdd:init` adds **only its own** line and never touches
another plugin's `--plugin-dir` line.

1. If `claude.sh` does **not** exist at the project root, do not create it here — the skeleton is
   `ds`-owned. Tell the user to run `/ds:init` first, then re-run `/sdd:init`.
2. If `claude.sh` exists, look for a `--plugin-dir` line pointing at `claude_plugins/sdd`.
   If it is absent, insert one immediately above the `"$@"` line, matching the form of the existing
   `--plugin-dir` lines and using the Step 3 `PLUGINS_ROOT` value:

   ```bash
     --plugin-dir "$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/sdd" \
   ```

3. If the line is already present, leave it — never duplicate it.

### 5b. Check the generic artifacts (detect-and-report)

Do not write these — only check them and warn if they're missing so the user knows to run `/ds:init`.

1. Confirm `claude.sh`'s launch line uses `CLAUDE_PLUGINS_LOADED=1`. If it is missing, tell the user to
   run `/ds:init`.
2. Confirm `.claude/settings.json` has a `SessionStart` hook checking `$CLAUDE_PLUGINS_LOADED`. If not,
   tell the user to run `/ds:init`. Do not add the hook here.

## Step 6: Validate the setup

Run these checks and report results:

1. Confirm `sdd` is in `enabledPlugins` in `.claude/settings.json`.
2. Confirm `Skill(sdd:*)` is in `permissions.allow`.
3. Confirm `.claude/sdd/config.md` exists and contains a `## Worktree Scripts` section with both the
   `Setup script` and `Teardown script` keys (blank values are valid).
4. Confirm `.claude/sdd/config.local.md` is listed in `.gitignore`.
5. Confirm `<PLUGINS_ROOT>/claude_plugins/sdd/` exists.
6. Confirm `claude.sh` contains the `sdd` `--plugin-dir` line (or that the user was told to run
   `/ds:init` first because `claude.sh` is missing).
7. Confirm the generic `ds`-owned artifacts (the `claude.sh` skeleton and the `SessionStart` hook) are
   present — and if not, that the user has been told to run `/ds:init`.
8. Report any issues found.

Print a summary of everything that was done. In the summary, explicitly point the user at
`.claude/sdd/config.md` and tell them to fill in the Worktree Scripts Setup and Teardown paths themselves.
