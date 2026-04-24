---
description: Initialise FLS plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize FLS Plugin

Set up the FLS Claude Code plugin for this project.

## Step 1: Merge recommended permissions into `.claude/settings.json`

1. Read `${CLAUDE_PLUGIN_ROOT}/templates/settings.json` for recommended permissions
2. If `.claude/settings.json` exists:
   - Read it and parse the existing permissions
   - Add any missing `allow` rules (don't duplicate existing ones)
   - Add any missing `deny` rules (don't duplicate existing ones)
   - Add `"fls": true` to `enabledPlugins` (create the key if it doesn't exist)
   - Merge the `SessionStart` hook from the template into the existing `hooks` section (create `hooks` if missing, add `SessionStart` if missing, append the command if an equivalent one isn't already there). Remove any other hook events (plugin owns those).
   - Write the updated file
3. If `.claude/settings.json` doesn't exist:
   - Create it from the template with `enabledPlugins: {"fls": true}` added
4. Report what was added/changed

## Step 2: Create `.claude/fls/config.md`

1. Ensure the `.claude/fls/` directory exists (create it if missing)
2. If `.claude/fls/config.md` already exists, skip this step
3. Ask the user for:
   - Dev admin email (default: `demodev@email.com`)
   - Dev admin password (default: `demodev@email.com`)
   - Base URL (default: `http://127.0.0.1:8000`)
4. Generate `.claude/fls/config.md` from `${CLAUDE_PLUGIN_ROOT}/templates/fls.md`, substituting the user's values

## Step 3: Create `.claude/fls/config.local.md`

1. If `.claude/fls/config.local.md` already exists, skip this step
2. Copy from `${CLAUDE_PLUGIN_ROOT}/templates/fls.local.md`

## Step 4: Update `.gitignore`

1. Read `.gitignore`
2. If `.claude/fls/config.local.md` is not already listed, add it
3. If `.claude/settings.local.json` is not already listed, check and add if missing

## Step 5: Determine FLS path

1. Ask the user for the relative path from the project root to FLS (e.g., `submodules/Freedom-LS`)
   - Default: `.` (for FLS itself, where the plugin is at `./fls-claude-plugin/`)
   - For concrete implementations, this is typically `submodules/Freedom-LS`
2. Validate that `<fls_path>/fls-claude-plugin/` exists
3. Store this path for use in wrapper script generation

## Step 6: Generate wrapper scripts

Wrapper scripts are installed in two locations:
- `claude.sh` — installed at the **project root** (it is the interactive entry point the user types frequently)
- All other wrappers — installed under `.claude/fls/scripts/` (create this directory if missing)

For each wrapper script template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/`:
1. Determine the destination: project root for `claude.sh`, otherwise `.claude/fls/scripts/`
2. Check if a script with that name already exists at the destination
3. If it exists, **skip it** (never overwrite existing scripts)
4. If it doesn't exist, copy the template to the destination, replace `__FLS_PATH__` with the path from Step 5, and make it executable

## Step 7: Clean up legacy CLAUDE.md plugin check

Earlier versions of this init command prepended a line to `CLAUDE.md` that asked Claude to check `$FLS_PLUGIN` on every session. That check is now handled by the `SessionStart` hook merged in Step 1, so the instruction line is obsolete.

1. Read `CLAUDE.md` at the project root (if it exists)
2. If it starts with a line mentioning `FLS_PLUGIN` (e.g., `If $FLS_PLUGIN is unset, stop and tell the user to run ./claude.sh instead of claude.`), remove that line and the blank line immediately following it
3. Otherwise skip this step

## Step 8: Validate the setup

Run these checks and report results:

1. Confirm `fls` is in `enabledPlugins` in `.claude/settings.json`
2. Confirm `.claude/fls/config.md` exists and contains required fields (email, password, base URL)
3. Confirm `claude.sh` exists at the project root and is executable
4. Confirm the other wrapper scripts exist under `.claude/fls/scripts/` and are executable
5. Confirm hook scripts in the plugin (`scripts/hooks/*.sh`) are executable
6. Confirm the only hook event under `.claude/settings.json` `hooks` is `SessionStart` (other hook events belong to the plugin)
7. Confirm wrapper scripts have the correct `FLS_PATH` (not `__FLS_PATH__`)
8. Confirm `.claude/settings.json` contains a `SessionStart` hook that checks `$FLS_PLUGIN`
9. Confirm `CLAUDE.md` no longer contains the legacy `FLS_PLUGIN` line (it has been superseded by the hook)
10. Report any issues found

Print a summary of everything that was done.
