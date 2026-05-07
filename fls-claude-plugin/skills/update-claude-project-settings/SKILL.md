---
name: update-claude-project-settings
description: Audit `.claude/settings.json` (shared project settings) for entries to add, remove, or rewrite, using `.claude/settings.local.json` as a hint for useful permissions. Only edits `.claude/settings.json`. Use when the user asks to "tidy up project settings", "audit project settings", or "promote permissions to project settings".
---

# Update Claude Project Settings

`.claude/settings.json` is checked in and shared by everyone working on the project. Over time it accumulates duplicate, overlapping, or stale entries — and useful permissions sometimes live only in a developer's local settings.

This skill audits the shared file and proposes cleanups. `.claude/settings.local.json` is read for context (to spot useful permissions worth promoting) but **never edited** — local settings belong to the user.

## Files

- **Project (shared, committed) — edited by this skill:** `.claude/settings.json`
- **Local (per-user, gitignored) — read only, never edited:** `.claude/settings.local.json`

## Process

### 1. Read both files

Read `.claude/settings.json` and `.claude/settings.local.json` in parallel. The local file is a reference only.

### 2. Audit `permissions.allow` in project settings for redundancy

Walk every entry in `.claude/settings.json` and look for:

- **Duplicates** — the same pattern appearing twice.
- **Subsumed entries** — a narrow pattern made redundant by a broader one in the same file (e.g. `Bash(npm run tailwind_build)` is subsumed by `Bash(npm run tailwind_build:*)`).
- **Stale entries** — patterns referencing scripts, paths, or commands that no longer exist in the repo. Spot-check before suggesting removal.
- **Too-narrow patterns** — entries so specific they only matched a one-off task and won't be useful again. Flag and suggest either broadening or removing.
- **Too-broad patterns** — entries that grant more than the project needs. Flag and suggest narrowing.

### 3. Scan local settings for promotion candidates

Walk `permissions.allow` in `.claude/settings.local.json` and classify each entry:

- **Promote** — generally useful for anyone working on the project (e.g. `Bash(uv run:*)`, `Bash(gh pr:*)`, project-relevant WebFetch domains, project commands). Suggest adding to project settings.
- **Already covered** — a broader rule in project settings already grants this. No action needed; mention if the local pattern suggests project settings should be broadened.
- **Keep local** — personal/exploratory/one-off (e.g. ad-hoc `curl` of a specific URL, exploratory WebFetch domains). Ignore.

Do not propose any edits to the local file. Only suggest additions to `.claude/settings.json`.

### 4. Ask the user, entry by entry

For each candidate (cleanup or promotion), ask a clear yes/no:

> Remove `Bash(npm run tailwind_build)` from project settings? (Subsumed by `Bash(npm run tailwind_build:*)`.) [y/n]

> Add `Bash(uv run:*)` to project settings? (Currently only in local settings.) [y/n]

Batch related entries if it makes sense (e.g. "Add these 8 documentation WebFetch domains?"), but do not silently bundle anything ambiguous.

### 5. Apply approved changes

Edit **only** `.claude/settings.json`. Preserve JSON formatting (2-space indent, trailing newline) to keep the diff clean.

### 6. Report

Summarise what was added, deleted, or rewritten in `.claude/settings.json`. Remind the user to commit the change. If useful permissions remain in local settings that they declined to promote, do not nag.

## Notes

- Never edit `.claude/settings.local.json` — that file belongs to the user.
- Never touch `deny` rules without explicit instruction — those are intentional safety boundaries.
- Never touch hooks, `enabledPlugins`, or `disabledMcpjsonServers` without explicit instruction — these are usually environment-specific.
- If a permission pattern looks too narrow or too broad to be useful project-wide, flag it and suggest a better pattern before adding.
