---
description: Fix one small bug on main, run the targeted tests, then commit and push
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Skill, AskUserQuestion
argument-hint: "<what is broken>"
---

Fix the bug in `$ARGUMENTS` in the main worktree and put it on `origin/main` in this run. This
command runs at **depth 0**, inline, and spawns no subagents.

A hotfix is **small**: one cause, a handful of files, a fix you can state in one sentence. Every
step below keeps it that way.

Other processes work in this worktree. Leave their uncommitted files as they are, and stage your
own by explicit path.

## Step 1: Check the branch

```
git branch --show-current
```

On any branch but `main` or `master`, stop and say so: a bug on a feature branch is fixed there.

## Step 2: Find the cause

Read the code the bug touches, and only that. Done when you can name the cause and the fix in one
sentence each.

Stop and recommend `/sdd:start` when the fix needs any of these:

- a database migration or a new dependency
- a decision about how the product should behave
- changes in more than a handful of files

## Step 3: Decide on a test

A test is for a behaviour bug that nothing covers yet. Take the first line that fits:

1. **No test.** The fix changes nothing a test can observe: wording, copy, a comment,
   documentation, a plugin or `CLAUDE.md` file, config no code path reads. Go to Step 4.
2. **Change an existing test.** A test already covers this code and missed the bug. Add the case
   to it: an assertion or a parametrize row, in the test function that is there.
3. **One new test**, when the bug is in behaviour and no existing test sits near it. Its name says
   what used to break.

On lines 2 and 3, load each skill under `## Testing Skills` in `.claude/sdd/config.md`
(`config.local.md` wins) with the `Skill` tool, then get to RED: run the test as the single test
run in the `Test tiers` file under `## Test Hooks` defines. A blank `Test tiers` runs the project's
plain test command for that one test. It must fail. If it passes, you have not reproduced the bug:
go back to Step 2.

## Step 4: Fix

Make the smallest change that fixes the bug. With a test from Step 3, run that single test again.
It must pass.

## Step 5: Targeted tier

Read `${CLAUDE_PLUGIN_ROOT}/commands/protected/run_test_tier.md` and follow it with `<tier>`:
`targeted` and `<diff>`: the explicit paths you created or changed.

- `tier: none` → nothing to run, continue.
- `tier: targeted` → done at a passing verdict. A failure follows "When a targeted run or full run
  fails" in the tier definition.
- `tier: full` → run nothing. The change reaches further than a hotfix should. Ask with
  `AskUserQuestion`: "The test selector wants the full suite for `<paths>`: `<why lines>`." Options:
  "Run the full suite", "Stop, I'll take this through `/sdd:start`".

## Step 6: Commit

```
git add <path> [<path> ...]
git commit -m "hotfix: <what was broken>" -- <path> [<path> ...]
```

The paths after `--` keep the commit to your own files: another process's staged files stay
staged and out of it. Commit as the project's `CLAUDE.md` says. The pre-commit hooks are a gate, so
`--no-verify` is out. When a hook rewrites a file, re-stage the same paths and commit again with
the same paths after `--`. When a hook fails on your
change, fix it and commit again.

## Step 7: Push

```
git push origin main
```

When origin rejects the push because it has moved:

```
git fetch origin main
git rebase origin/main
git push origin main
```

Git refuses to start the rebase while another process has unstaged edits to tracked files in
this worktree; that is expected here, not a fault to work around. If git refuses to start the
rebase, report its message. If the rebase stops on a conflict, run
`git rebase --abort`. Either way stop there and report `local only`: the commit is on local `main`
and the user decides what happens next. No force-push and no stash.

## Step 8: Document, if a doc is now wrong

Search the project's documentation for the behaviour the fix changed. A fix that restores what the
docs already describe needs nothing. When a doc now says something false, correct those lines and
commit them as in Step 6, with the doc paths after `--` and the message
`hotfix: document <what changed>`, then push as in Step 7.

## Step 9: Report

- the commit sha, and `pushed` or `local only` with git's message
- the test changed or added, or `no test: <reason>`
- the tier that ran and its verdict line
- the doc changed, or `no doc needed`
