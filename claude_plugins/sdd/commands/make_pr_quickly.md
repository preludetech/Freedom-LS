---
description: Open a pull request for the current branch immediately, with no checks, rebase, tests or commits
allowed-tools: Bash
---

Open a pull request for the current branch **right now**. Nothing comes first.

The user wants the PR to exist. The title and body do not matter. Speed is the only goal.

## Never

- rebase, fetch, or run the pre-step rebase
- run tests, linters, type checkers, pre-commit, or migrations
- make, amend, or stash commits, or touch uncommitted changes
- edit or tick `todo.md` or any other file
- read the spec, plan, todo, or any source file
- spawn subagents or invoke other commands or skills
- ask the user anything

## Steps

Run this as a single Bash call:

```
git push -u origin HEAD && gh pr create --base main --fill
```

`--fill` takes the title and body from the commits, so nothing has to be written.

- If the push is rejected because the remote branch has diverged (for example after a local
  rebase), retry once with `git push -u origin HEAD --force-with-lease --force-if-includes`, then
  run `gh pr create --base main --fill`.
- If `gh pr create` says a pull request already exists for the branch, that's fine. Get its URL with
  `gh pr view --json url -q .url`.

## Report

One line: the PR URL. Nothing else.
