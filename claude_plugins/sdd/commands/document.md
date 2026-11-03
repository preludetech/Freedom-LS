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
hooks: report that and go to Step 2b. Each bullet is `<label>: <skill>`. For each, in order:

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

## Step 2b: Run the documentation items

Read `<todo-path>`. Every unticked item in the section `## 4. Documentation and pull request`
that sits between the item naming `/sdd:document` and the item naming `/sdd:make_pr_quickly`
is a documentation task, whatever its marker. An item whose commit subject
`<spec name>: <item text>` is already on the branch (`git log --format=%s origin/main..HEAD`)
is ticked, not re-run. For each other one, in order, spawn one sub-agent
(`subagent_type: "general-purpose"`, `model: "sonnet"`) briefed with: the item text, the spec
path, the `Comment standard` file from `## Review Hooks` (blank names nothing), and the rule
that it commits its own work with the project's commit command as `<spec name>: <item text>`,
passing the subject through `-F` from a file or a quoted heredoc and never interpolating it
into a command string, and returns `status: ok|failed|blocked · reason: <short>`. One
sub-agent at a time: they share the worktree and each commits.

- `ok`: delegate the tick to `sdd:sdd-mechanic` via
  `${CLAUDE_PLUGIN_ROOT}/commands/protected/update_todo.md` with `tick:"<item text>"`.
- `failed`: retry twice with the prior error.
- `blocked`, or still failed: leave the item unticked and carry its reason to Step 4.

No items: say so.

## Step 3: Tick and commit

Read `<todo-path>`. If it has an unchecked item naming `/sdd:document`, delegate to
`sdd:sdd-mechanic`: invoke `${CLAUDE_PLUGIN_ROOT}/commands/protected/update_todo.md` with
`<todo-path>` and `tick:"Run `/sdd:document`"`, then `commit_and_push.md` with `<summary>`:
`run the documentation hooks`, staging `todo.md`. A checklist from an older layout has no such
item: skip the tick and say so in Step 4.

## Step 3b: Open the pull request

Read `${CLAUDE_PLUGIN_ROOT}/commands/make_pr_quickly.md` and follow it inline, whatever Steps 2
and 2b left outstanding. It takes no hook-mode input: it has no rebase or tick to skip, and its
"Never" list holds inside it. The tick and the commit below are this command's own steps after
it returns. When it prints a PR URL: delegate to `sdd:sdd-mechanic` to tick the
`/sdd:make_pr_quickly` item via `update_todo.md`, then `commit_and_push.md` with `<summary>`:
`open the pull request`, staging `todo.md`. When it prints a `gh` error, carry it to Step 4 and
tick nothing.

## Step 4: Report

One line per hook: `<label>: ok|failed|needs-approval · <what it changed, or "no change">`. For
each `needs-approval` hook, give its reason and the uncommitted files the user has to decide on.
One line per documentation task: `<item text>: done|skipped: <reason>`. Then the PR URL or the `gh`
error.
