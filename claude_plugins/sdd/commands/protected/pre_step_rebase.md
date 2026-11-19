---
description: Helper — rebase the feature branch onto main and verify it before an SDD step runs
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
---

This is a helper command. Every feature-branch command follows this helper as its own Step 0; a
command run in hook mode skips it, and `register_design`, which only adds spec files, never runs it. It runs at **depth 0**,
inline, on the caller's model and tool grants.

Inputs from the caller: `<spec-dir>` and `<todo-path>` when already known; otherwise `<spec-dir>` is
the directory under `spec_dd/2. in progress/` named after the current branch (none or several is
`status: failed` with the reason), and `<todo-path>` is its `todo.md`. Optionally `<tier>`, `none`, `targeted` or `full`:
the test tier the rebase runs.

## Step 0: Skip conditions

```
git branch --show-current
```

On `main` or `master` → `status: ok · reason: on main`. Stop.

If no spec directory under `spec_dd/2. in progress/` matches the branch → the same: `status: ok ·
reason: no spec directory`. Stop.

### Pause condition

Read `<todo-path>`. If it has an unticked (`- [ ]`) item whose text names
`upstream_change_review.md`, an earlier rebase already paused this spec on a decision the human
has not made yet:

```
status: paused · reason: upstream-change review awaiting a decision
```

Print `<spec-dir>/upstream_change_review.md` so the caller knows where to look, then stop. Nothing
is fetched or rebased while paused.

## Step 1: Rebase

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists — its values take
precedence). Under `## Rebase Hooks`, look at the `Rebase command` value:

- blank, or the file or section absent → `status: ok · reason: no rebase command`. Stop.
- a non-blank path → read that file and follow its steps here with `<tier>`: the value the caller
  passed, or `targeted` when it passed none, and `<auto-resolve>`: the list in
  `claude_plugins/sdd/resources/rebase_auto_resolve.md`, with `<own-spec-dir>` set to `<spec-dir>`.

Once it returns:

- `rebased: no` → `status: ok · reason: up to date`. Stop.
- `failed` or `blocked` → return that status and its reason as this helper's own. The caller stops.
- otherwise, keep `old-base`, `old-tip` and `tier` from its return contract for the steps below.

## Step 2: Front-end check

Read the config as Step 1 does. Under `## Rebase Hooks`, look at the `Front-end check` value:

- blank, or the file or section absent → skip this step.
- a non-blank path → read that file and follow its steps with `<old-base>` and `<spec-dir>`.

Once it returns:

- `failed` → return `status: failed` with its reason as this helper's own. The caller stops.
- `ok` with commits made → push them: `git push`. The rebase already force-pushed the branch in
  Step 1, so this is a plain fast-forward on top of it.

## The `PLUGINS_ROOT` rule

`PLUGINS_ROOT` is the relative path from the project root to the checkout holding
`claude_plugins/`. Take the first that yields a value:

1. The `PLUGINS_ROOT="…"` line in `claude.sh` at the project root.
2. The `PLUGINS_ROOT="…"` line in any `.sh` under `.claude/*/scripts/` whose value is not
   `__PLUGINS_ROOT__`. Two that disagree → `status: failed · reason: conflicting PLUGINS_ROOT
   values`; stop.
3. `.`.

When it is `.`, write script paths with no `./` prefix, to match the project's allow entry.

## After Step 2

When Step 1's rebase returned `rebased: yes`, read
`claude_plugins/sdd/resources/upstream_change_review.md` and follow it with `<old-base>`,
`<spec-dir>` and `<todo-path>`; its final status line is this helper's return. Step 0, `rebased: no`,
no rebase command, a `failed` or `blocked` rebase and a `failed` Step 2 stop first.

## Return contract

```
status: ok|paused|failed|blocked · rebased: yes|no · tier: none|targeted|full · reason: <short>
```

`tier` is the tier the rebase command reported, or `none` when the rebase stopped early. A caller
continues only on `ok`. On any other status it relays the reason and stops.
