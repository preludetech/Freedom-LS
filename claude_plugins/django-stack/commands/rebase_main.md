---
description: Rebase the current branch onto main, resolve conflicts, verify, and push
allowed-tools: Bash, Read, Edit, Grep, Glob
---

Rebase the current branch onto `main`, resolve any conflicts, verify the result, and push. This
command runs to completion without asking for confirmation along the way; it only stops to report
`status: ok`, `status: failed`, or `status: blocked`.

Input from the caller: `<tier>`, `targeted` or `full`. Run by hand or without a value, it is
`targeted`.

## Step 1: Check the branch

```
git branch --show-current
```

If you are already on `main` or `master`, tell the user there is nothing to rebase and stop.

```
git rev-parse --abbrev-ref @{upstream}
```

Note whether the branch has an upstream. Step 12 needs this to decide whether to push at all.

## Step 2: Commit what is in flight

```
git status --porcelain
```

If this is empty, skip to Step 3. Otherwise:

```
git add -A
uv run git commit -m "<branch>: wip before rebase onto main"
```

A commit, rather than a stash, means the lost-change check in Step 7 covers this work the same way
it covers every other commit on the branch. This wip commit is not meant to be squashed away later;
it rides through to the pull request as-is.

If a hook rejects the commit, work through it rather than stopping:

- A formatter rewrote files (for example `ruff-format`, trailing whitespace, end-of-file fixes) →
  re-stage those files and retry.
- A check reported a fixable error (`mypy`, `ruff check`, `bandit`, `shellcheck`) → read only the
  files it named, make the minimal correct fix, re-stage, retry.
- A secret was flagged → read the line. A real credential means stop and tell the user now. A false
  positive means remove the literal, or add the tool's own allowlist marker where the wording can't
  avoid it.
- Anything else, including an attempt that fails identically to the one before it → stop with
  `status: blocked`. Nothing has been rebased yet.

Up to five attempts. Never pass `--no-verify`.

## Step 3: Fetch, and stop early when there is nothing to do

```
git fetch origin main
git merge-base --is-ancestor origin/main HEAD
```

If this succeeds, `origin/main` is already in the branch's history. Print "branch already contains
origin/main" and stop with:

```
status: ok · rebased: no
```

## Step 4: Record the starting point

```
OLD_BASE=$(git merge-base origin/main HEAD)
git log --merges --oneline $OLD_BASE..HEAD
```

If this prints anything, stop with `status: blocked`. A rebase replays only a merge commit's first
parent and drops the rest without a conflict, so a human has to decide what to do with it.

Then check that no other worktree is halfway through merging this branch:

```
common=$(git rev-parse --git-common-dir)
cat "$common"/MERGE_HEAD "$common"/worktrees/*/MERGE_HEAD 2>/dev/null
```

If any printed sha equals `git rev-parse HEAD`, stop with `status: blocked · reason: a worktree
has a merge of this branch in progress; finish or abort it there first`. Rewriting the branch now
would orphan that merge: its MERGE_HEAD would point at a commit no branch holds, and whoever
started it would be left with a conflicted tree and nothing to finish it against.

Otherwise, record the branch's current tip before rewriting it:

```
OLD_TIP=$(git rev-parse HEAD)
```

## Step 5: Rebase

```
git rebase origin/main
```

## Step 6: Resolve conflicts

If the rebase stops on a conflict:

1. Run `git diff --name-only --diff-filter=U` to list the conflicted files.
2. Read each one and resolve it using the surrounding code, keeping both sides' intent where
   possible and preferring the branch's own logic where the change was clearly intentional.
3. Stage the resolved file with `git add <file>`.
4. Continue with `GIT_EDITOR=true git rebase --continue`.
5. Repeat until the rebase completes.

A few rules on top of that loop:

- During a rebase, `--ours` means `origin/main`'s side and `--theirs` means the branch's own
  commit. That is the reverse of what those flags mean in a normal merge. A wholesale
  `git checkout --ours <file>` or `--theirs <file>` is only ever right for a generated file.
- `uv.lock` and `package-lock.json` are never hand-merged. Resolve `pyproject.toml` or
  `package.json` first, then regenerate the lockfile with `uv lock` or
  `npm install --package-lock-only`, then `git add` it.
- A branch migration numbered the same as a new one on `main`: `git mv` the branch's migration so it
  sorts after `main`'s latest migration for that app (the old path's removal and the new path land
  in the same staged change), point its `dependencies` at `main`'s leaf migration, and fix any later
  branch migration that depended on the old name. Never run `makemigrations --merge`. Step 7
  lists the renamed migration under `REVIEW:` as its old and new path.
- Stop with `status: blocked` when both sides made substantive, incompatible changes to the same
  logic; when a resolution would need `--ours` or `--theirs` on a file that isn't generated; or when
  a conflict lands in a file none of the branch's own commits meant to change.

## Step 7: Lost-change check

First record the replayed tip. Every commit this step adds (a restored hunk, one of main's changes
put back, a renumbered migration) lands after it, and Step 9 re-tests exactly those:

```
REPLAYED_TIP=$(git rev-parse HEAD)
.claude/ds/scripts/rebase_lost_change_check.sh $OLD_BASE $OLD_TIP
```

Read the exit code:

- `0` → lost-change check: pass. Continue to Step 8.
- `1` → for each path under `LOST:`, restore the branch's own change from the old tip:
  `git diff $OLD_BASE $OLD_TIP -- <file>` is the hunk to re-apply. Commit it as
  `uv run git commit -m "<branch>: restore <what> lost in rebase"`, then re-run the script.
- `2` → read the range-diff printed for each path under `REVIEW:`. A benign difference is
  context drift; a `-`/`+` pair inside a commit that never meant to touch that code is a
  dropped or altered change, restored the same way as for exit `1`. Then check the file
  against `git diff $OLD_BASE origin/main -- <file>`: the branch may only remove a line
  `main` added where the branch's own commit meant to remove it.

  Two kinds of `REVIEW:` path need their own handling:

  - A path that is absent from `git diff --name-only --no-renames $OLD_BASE $OLD_TIP` belongs to a file the
    branch never changed, so it must match `origin/main`. Any difference means conflict resolution
    undid main's change. Restore it with `git checkout origin/main -- <file>`, then
    commit as `uv run git commit -m "<branch>: restore main's <what> reverted in rebase"`.
  - A migration renumbered in Step 6 appears as both its old and its new path. Compare them with
    `git diff $OLD_TIP:<old path> HEAD:<new path>`. The only allowed differences are the number
    and `dependencies`.

Then run:

```
uv run manage.py makemigrations --check --dry-run
```

"No changes detected" is the only pass. Anything else means the Step 6 migration renumbering
is incomplete: fix it and commit.

## Step 8: Rebuild and migrate

Read `.claude/ds/config.md` (and `.claude/ds/config.local.md` if it exists; its values take
precedence). Under `## Rebase Scripts`, the `Rebuild script` value:

- non-blank path → run it from the project root. A non-zero exit is `status: failed`.
- blank, or the file or section absent → skip.

Then:

```
uv run manage.py migrate
```

## Step 9: Run the tests

Follow `${CLAUDE_PLUGIN_ROOT}/resources/test_tiers.md`; every command below is one of its tiers.

`<tier>` is `full` → run the full tier.

`<tier>` is `targeted` →

1. The branch's diff:

       .claude/ds/scripts/select_tests.sh --range origin/main..HEAD

   `tier: none` → the branch holds nothing a test can see. Report `tier: none`; go to Step 10.
2. Main's diff and the fix-ups committed since the replay, with the branch's own tests:

       .claude/ds/scripts/select_tests.sh --range $OLD_BASE..origin/main --range $REPLAYED_TIP..HEAD --tests-changed-in origin/main..HEAD

   `tier: none` → main brought in nothing the branch's code can interact with, and Step 7 added
   nothing a test can see. Report `tier: none`. Otherwise run the printed command.

A failure is fixed on the branch, test first, following "When a targeted run or full run fails"
in the tier definition, then committed:

```
uv run git commit -m "<branch>: fix <what> after rebase"
```

Three attempts. If the run still fails after that, stop with `status: failed`.

## Step 10: Pre-commit

```
uv run pre-commit run --all-files
```

Fix any failures and re-run until clean.

## Step 11: Summarise

Report:

- how many commits were replayed
- any conflicts that were resolved, and how
- the tier that ran, and any test failures that were fixed
- the lost-change check's result

## Step 12: Push

No upstream (from Step 1) → say so and skip this step.

```
git push origin HEAD --force-with-lease --force-if-includes
```

Push without asking, once tests and pre-commit are clean. Keep both flags after the refspec: a rule
that blocks `git push --force:*` is a prefix match, and `--force-with-lease` shares that prefix.

If the push is rejected, the remote moved since Step 3's fetch. Stop with `status: failed`. Never
retry with plain `--force`.

## Return contract

A caller that reads and follows this file inline gets the result from this line:

```
status: ok|failed|blocked · rebased: yes|no · old-base: <sha> · old-tip: <sha> ·
replayed: <n> · conflicts: <n> · lost-change check: pass|fixed ·
tier: none|targeted|full · pushed: yes|no · reason: <short>
```

This file carries no `model:` frontmatter. A caller that reads and follows it inline runs it on its
own model.
