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
   - Remove the `hooks` section if present (plugin now owns hooks)
   - Write the updated file
3. If `.claude/settings.json` doesn't exist:
   - Create it from the template with `enabledPlugins: {"fls": true}` added
4. Report what was added/changed

## Step 2: Create `.claude/fls.md`

1. If `.claude/fls.md` already exists, skip this step
2. Ask the user for:
   - Dev admin email (default: `demodev@email.com`)
   - Dev admin password (default: `demodev@email.com`)
   - Base URL (default: `http://127.0.0.1:8000`)
3. Generate `.claude/fls.md` from `${CLAUDE_PLUGIN_ROOT}/templates/fls.md`, substituting the user's values

## Step 3: Create `.claude/fls.local.md`

1. If `.claude/fls.local.md` already exists, skip this step
2. Copy from `${CLAUDE_PLUGIN_ROOT}/templates/fls.local.md`

## Step 4: Update `.gitignore`

1. Read `.gitignore`
2. If `.claude/fls.local.md` is not already listed, add it
3. If `.claude/settings.local.json` is not already listed, check and add if missing

## Step 5: Determine FLS path

1. Ask the user for the relative path from the project root to FLS (e.g., `submodules/Freedom-LS`)
   - Default: `.` (for FLS itself, where the plugin is at `./fls-claude-plugin/`)
   - For concrete implementations, this is typically `submodules/Freedom-LS`
2. Validate that `<fls_path>/fls-claude-plugin/` exists
3. Store this path for use in wrapper script generation

## Step 6: Generate wrapper scripts at project root

For each wrapper script template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/`:
1. Check if a script with that name already exists at the project root
2. If it exists, **skip it** (never overwrite existing scripts)
3. If it doesn't exist, copy the template to the project root, replace `__FLS_PATH__` with the path from Step 5, and make it executable

## Step 7: Validate the setup

Run these checks and report results:

1. Confirm `fls` is in `enabledPlugins` in `.claude/settings.json`
2. Confirm `.claude/fls.md` exists and contains required fields (email, password, base URL)
3. Confirm wrapper scripts exist at project root and are executable
4. Confirm hook scripts in the plugin (`scripts/hooks/*.sh`) are executable
5. Confirm no `hooks` section in `.claude/settings.json`
6. Confirm wrapper scripts have the correct `FLS_PATH` (not `__FLS_PATH__`)
7. Report any issues found

Print a summary of everything that was done.
