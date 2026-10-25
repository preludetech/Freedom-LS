---
description: Open a pull request for the current branch immediately, with no checks, rebase, tests or commits
allowed-tools: Bash
---

Open a pull request for the current branch **right now**. Nothing comes first.

The user wants the PR to exist. The title and body do not matter. Speed is the only goal.

Local state never blocks the PR. A rebase in progress, a detached HEAD, a rejected push or
uncommitted changes are not reasons to stop or to report back without a PR. The branch already on
the remote is good enough: open the PR from it.

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
g=$(git rev-parse --git-dir); b=$(git branch --show-current)
[ -z "$b" ] && b=$(sed 's#^refs/heads/##' "$g"/rebase-merge/head-name "$g"/rebase-apply/head-name 2>/dev/null | head -1)
[ -n "$(git branch --show-current)" ] && git push -u origin HEAD
gh pr create --head "$b" --base main --title "$b" --body "" || gh pr view "$b" --json url -q .url
```

- The branch name comes from the rebase state when HEAD is detached mid-rebase.
- The push runs only when a branch is checked out, and its failure is ignored: the PR is opened
  from whatever the remote branch holds.
- `gh pr view` prints the URL when a PR already exists for the branch.
- If that call prints no URL, report the `gh` error. Do not retry the push or force it.

## Report

One line: the PR URL. Nothing else.
