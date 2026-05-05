---
name: update-claude-project-settings
description: Audit `.claude/settings.local.json` for entries that belong in the shared `.claude/settings.json` (project settings) and migrate them with user approval. Use when the user asks to "promote", "share", "move to project settings", or "tidy up local settings".
---

# Update Claude Project Settings

`@.claude/settings.local.json` is per-user and gitignored. `@.claude/settings.json` is checked in and shared by everyone working on the project. Useful permissions accumulated locally should be promoted so the whole team benefits.

This skill walks the local settings, classifies each entry, and asks the user one-by-one whether to move it across.

## Files

- **Local (per-user, gitignored):** `.claude/settings.local.json`
- **Project (shared, committed):** `.claude/settings.json`

## Process

### 1. Read both files

Read `.claude/settings.json` and `.claude/settings.local.json` in parallel.

### 2. Classify every entry in local settings

For each entry under `permissions.allow` (and any other top-level key), decide one of:

- **Promote** — generally useful for anyone working on the project (e.g. `Bash(uv run:*)`, `Bash(gh pr:*)`, project-relevant WebFetch domains, project commands).
- **Keep local** — personal/exploratory/one-off (e.g. ad-hoc `curl` of a specific URL, a one-shot `awk` recipe, personal preferences like `disabledMcpjsonServers`, exploratory WebFetch domains).
- **Already covered** — a broader rule in project settings already grants this (e.g. local has `Bash(npm run tailwind_build:*)` but project has `Bash(npm run tailwind_build)` — note the difference and ask).
- **Redundant** — duplicate of something already in project settings; just delete from local.

Skip entries already present verbatim in project settings.

### 3. Audit project settings for redundancy

Walk `permissions.allow` in `.claude/settings.json` and look for:

- **Duplicates** — the same pattern appearing twice.
- **Subsumed entries** — a narrow pattern made redundant by a broader one in the same file (e.g. `Bash(npm run tailwind_build)` is subsumed by `Bash(npm run tailwind_build:*)`).
- **Stale entries** — patterns referencing scripts, paths, or commands that no longer exist in the repo. Spot-check before suggesting removal.

For each candidate, ask the user before deleting.

### 4. Ask the user, entry by entry

For each candidate to **Promote** or **Already covered**, ask the user a clear yes/no:

> Move `Bash(uv run:*)` to project settings? (Currently only in local.) [y/n]

Batch related entries if it makes sense (e.g. "Move all 8 WebFetch domains for documentation sites?"), but do not silently bundle anything ambiguous.

For **Keep local** entries: do not ask — leave them alone.

For **Redundant** entries in local: mention them and ask if they should be removed from local.

For project-settings cleanup candidates from step 3: ask before deleting each one (or each batch).

### 5. Apply approved changes

For each approval:
- Promotions: add to `.claude/settings.json` and remove from `.claude/settings.local.json`.
- Local redundancies: remove from `.claude/settings.local.json`.
- Project cleanup: remove from `.claude/settings.json`.

Preserve JSON formatting (2-space indent, trailing newline) to keep the diff clean.

### 6. Report

Summarise what moved, what stayed, and what was deleted from each file. Remind the user the project settings change should be committed.

## Notes

- Never move `deny` rules without explicit instruction — those are intentional safety boundaries.
- Never move hooks, `enabledPlugins`, or `disabledMcpjsonServers` without explicit instruction — these are usually environment-specific.
- If `.claude/settings.local.json` does not exist, there is nothing to do.
- If a permission pattern looks too narrow or too broad to be useful project-wide, flag it and suggest a better pattern before promoting.
