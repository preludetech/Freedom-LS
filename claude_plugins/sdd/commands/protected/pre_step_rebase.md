---
description: Helper — rebase the feature branch onto main and verify it before an SDD step runs
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
---

This is a helper command. `/sdd:next` follows it inline before dispatching a `(cmd)` item, and every
feature-branch command follows it as its own Step 0 when invoked directly. It runs at **depth 0**,
inline, on the caller's model and tool grants.

Inputs from the caller: `<spec-dir>` and `<todo-path>` when already known; otherwise resolve them the
way `claude_plugins/sdd/commands/next.md` Step 1 does.

## Step 0: Skip conditions

```
git branch --show-current
```

On `main` or `master` → `status: ok · reason: on main`. Stop.

If no spec directory under `spec_dd/2. in progress/` matches the branch → the same: `status: ok ·
reason: no spec directory`. Stop.

### Pause condition

Filled in by a later change.

## Step 1: Rebase

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists — its values take
precedence). Under `## Rebase Hooks`, look at the `Rebase command` value:

- blank, or the file or section absent → `status: ok · reason: no rebase command`. Stop.
- a non-blank path → read that file and follow its steps here.

Once it returns:

- `rebased: no` → `status: ok · reason: up to date`. Stop.
- `failed` or `blocked` → return that status and its reason as this helper's own. The caller stops.
- otherwise, keep `old-base` and `backup` from its return contract for the steps below.

## Step 2: Front-end check

Filled in by a later change.

## Step 3: Upstream-change scan

Filled in by a later change.

## Return contract

```
status: ok|paused|failed|blocked · rebased: yes|no · reason: <short>
```

A caller continues only on `ok`. On any other status it relays the reason and stops.
