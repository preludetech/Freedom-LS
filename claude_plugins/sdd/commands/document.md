---
description: Run the project's documentation hooks for the current spec, in config order
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, ToolSearch, mcp__playwright__*, mcp__plugin_ds_playwright__*
---

Runs at depth 0. Each hook is read and followed inline, so it runs on this command's model and
tool grants, and any worker or mechanic it spawns uses this command's `Agent` tool. The tool
list is the union of what the project's hooks need; the browser tools are here because a
documentation hook may take screenshots.

## Step 0: Pre-step rebase

Read `${CLAUDE_PLUGIN_ROOT}/commands/protected/pre_step_rebase.md` and follow its steps.

## Step 1: Resolve the spec directory

Resolve `<spec-dir>` and `<todo-path>` the way `pre_step_rebase.md`'s "Inputs from the caller"
line says.

## Step 2: Run the hooks

Read `## Documentation Hooks` in `.claude/sdd/config.md` (and `config.local.md`; a non-empty
list there replaces the whole list). An empty list, or an absent section or file, means no
hooks: report that and go to Step 3. For each bullet `<label>: <path>`, in order:

1. Record `git status --porcelain`.
2. Read `<path>` and follow it here with `<spec-dir>`, `<todo-path>` and `mode: hook`.
3. Record its status. A `failed` hook is reported with its reason and the next one runs.
4. Run `git status --porcelain` again. The paths that are new or changed since item 1 are the
   hook's; when there are none, the hook committed its own work or changed nothing. Otherwise
   delegate to `sdd:sdd-mechanic`: read `${CLAUDE_PLUGIN_ROOT}/resources/commit_and_push.md`
   and follow it with `<summary>`: `<label>`, staging exactly those paths.

## Step 3: Tick and commit

Delegate to `sdd:sdd-mechanic`: invoke `${CLAUDE_PLUGIN_ROOT}/commands/protected/update_todo.md`
with `<todo-path>` and `tick:"Run `/sdd:document`"`, then `commit_and_push.md` with
`<summary>`: `run the documentation hooks`, staging `todo.md`.

## Step 4: Report

One line per hook: `<label>: ok|failed · <what it changed, or "no change">`.
