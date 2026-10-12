---
description: Run the project's documentation hooks for the current spec, in config order
allowed-tools: Read, Glob, Bash, Skill, Agent
---

Runs at depth 0. Each hook is a skill from whichever plugin owns it, invoked with the `Skill`
tool, so it runs with its own plugin root and its own tool grants.

## Step 0: Pre-step rebase

Read `${CLAUDE_PLUGIN_ROOT}/commands/protected/pre_step_rebase.md` and follow its steps.

## Step 1: Resolve the spec directory

Resolve `<spec-dir>` and `<todo-path>` the way `pre_step_rebase.md`'s "Inputs from the caller"
line says.

## Step 2: Run the hooks

Read `## Documentation Hooks` in `.claude/sdd/config.md` (and `config.local.md`; a non-empty
list there replaces the whole list). An empty list, or an absent section or file, means no
hooks: report that and go to Step 3. Each bullet is `<label>: <skill>`. For each, in order:

1. Invoke `<skill>` with the `Skill` tool, with
   `args: "spec-dir=<spec-dir> todo-path=<todo-path> mode: hook"`, and follow it to the end.
2. In hook mode a hook ends in one of these ways:
   - it committed its own work, or changed nothing;
   - it ends its report with `changed: <path> …`: delegate to `sdd:sdd-mechanic` to read
     `${CLAUDE_PLUGIN_ROOT}/resources/commit_and_push.md` and follow it with `<summary>`:
     `<label>`, staging exactly those paths and nothing else;
   - `status: needs-approval` with a reason: commit nothing, and keep the reason and the files it
     names for Step 4;
   - `status: failed` with a reason.
3. A `failed` or `needs-approval` hook does not stop the run; the next hook runs.

## Step 3: Tick and commit

Read `<todo-path>`. If it has an unchecked item naming `/sdd:document`, delegate to
`sdd:sdd-mechanic`: invoke `${CLAUDE_PLUGIN_ROOT}/commands/protected/update_todo.md` with
`<todo-path>` and `tick:"Run `/sdd:document`"`, then `commit_and_push.md` with `<summary>`:
`run the documentation hooks`, staging `todo.md`. A checklist from an older layout has no such
item: skip the tick and say so in Step 4.

## Step 4: Report

One line per hook: `<label>: ok|failed|needs-approval · <what it changed, or "no change">`. For
each `needs-approval` hook, give its reason and the uncommitted files the user has to decide on.
