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

Read `<todo-path>`. If it has an unticked (`- [ ]`) item whose text names
`upstream_change_review.md`, an earlier rebase already paused this spec on a decision the human
has not made yet:

```
status: paused · reason: upstream-change review awaiting a decision
```

Print `<spec-dir>/upstream_change_review.md` so the caller knows where to look, then stop. Nothing
is fetched or rebased while paused — the human has to act first.

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

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists — its values take
precedence), the same way Step 1 does. Under `## Rebase Hooks`, look at the `Front-end check` value:

- blank, or the file or section absent → skip this step.
- a non-blank path → read that file and follow its steps with `<old-base>` and `<spec-dir>`.

Once it returns:

- `failed` → return `status: failed` with its reason as this helper's own. The caller stops.
- `ok` with commits made → push them: `git push`. The rebase already force-pushed the branch in
  Step 1, so this is a plain fast-forward on top of it.

## Step 3: Upstream-change scan

```
claude_plugins/sdd/scripts/upstream_change_scan.sh <old-base> origin/main "<spec-dir>" \
  > .sdd-work/rebase_upstream_scan.md
```

Delete any `.sdd-work/rebase_upstream_review.md` left behind by an earlier rebase, by name. A
fresh scan means a fresh review — a stale review from an interrupted run must never be reused
against a different scan.

- exit 0 → delete `.sdd-work/rebase_upstream_scan.md` by name. `status: ok · rebased: yes`. Stop.
- exit 2 → go to Step 4.

## Step 4: Upstream-change review

If `.sdd-work/rebase_upstream_review.md` already exists and ends `status: ok`, this is a resumed
run — reuse it and skip straight to Step 5.

Otherwise spawn **one** `sdd:sdd-worker` as its own solo `Agent` call. Its brief:

- Read `.sdd-work/rebase_upstream_scan.md`, the spec directory's own artifacts (`idea.md`,
  `1. spec.md`, `2. plan.md`, whichever exist — the scan file's commit list shows how far
  implementation has got through any `[batch N]` commits it lists), `docs/app_structure.md` and
  `CLAUDE.md`.
- Decide `direction: unchanged` or `direction: changed`. `changed` means the upstream change
  alters an app boundary in `docs/app_structure.md`, a shared base the spec builds on, a skill or
  convention the spec's plan contradicts, or a finished spec in `spec_dd/3. done/` that took a
  decision this spec reopens. Size alone is never `changed`.
- Write `.sdd-work/rebase_upstream_review.md` in a single `Write`:

  ```
  # Upstream-change review: <spec name>

  direction: unchanged | changed

  ## What main gained
  one paragraph per signal that fired, in this project's words

  ## Why it matters for this spec            (only when changed)
  which of the spec's decisions the upstream change undercuts, and the artifact that holds
  each: idea.md, 1. spec.md, 2. plan.md, or an implemented batch

  ## What to change                          (only when changed)
  one bullet per artifact, concrete enough to edit from

  status: ok
  ```

Resume and retry within this run, per the fan-out recipe: `failed` retries the same worker up to
twice, with the prior error folded into the retry brief; `blocked` supplies the listed `needs`
from the scan file or the code before retrying. Still `failed` or `blocked` after that:

```
status: failed · reason: upstream-change review <worker reason>
```

Leave `.sdd-work/rebase_upstream_scan.md` and any partial `.sdd-work/rebase_upstream_review.md` in
place — do not delete either on this exit. The next run's Step 3 replaces the scan file and this
step resumes from whatever review survives.

## Step 5: Act on the verdict

Read `direction:` from `.sdd-work/rebase_upstream_review.md`.

**`unchanged`** — delete `.sdd-work/rebase_upstream_scan.md` and
`.sdd-work/rebase_upstream_review.md` by name.

```
status: ok · rebased: yes
```

**`changed`** —

1. Move `.sdd-work/rebase_upstream_review.md` to `<spec-dir>/upstream_change_review.md`,
   replacing an earlier one there if one exists.
2. Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/commands/protected/update_todo.md` and
   follow its steps with `<todo-path>` and `add_first:"user|Decide what to change after reading
   upstream_change_review.md, then edit the idea, spec or plan it names"`.
3. Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and
   follow its steps with `<summary>`: `record the upstream-change review`, staging
   `upstream_change_review.md` and `todo.md`.
4. Delete `.sdd-work/rebase_upstream_scan.md` by name.

```
status: paused · reason: upstream-change review awaiting a decision
```

When the human later ticks that item through `/sdd:next`, the next pre-step rebase's Pause
condition finds no unticked item naming the file, so it proceeds normally. The review file stays
in the spec directory as a sibling of the spec, like any research file.

## Return contract

```
status: ok|paused|failed|blocked · rebased: yes|no · reason: <short>
```

A caller continues only on `ok`. On any other status it relays the reason and stops.
