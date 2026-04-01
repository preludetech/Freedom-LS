Rebase the current branch onto `main`, resolve any conflicts, and verify everything works.

## Step 1: Check current branch

Run `git branch --show-current`. If you are already on `main`, tell the user there is nothing to rebase and stop.

## Step 2: Fetch and update main

```
git fetch origin main
git rebase origin/main
```

## Step 3: Resolve merge conflicts

If the rebase stops due to merge conflicts:

1. Run `git diff --name-only --diff-filter=U` to list conflicted files
2. Read each conflicted file and resolve the conflicts using the surrounding code context — keep both sides' intent where possible, prefer the feature branch's logic when the change is intentional
3. Stage the resolved file with `git add <file>`
4. Continue the rebase with `git rebase --continue`
5. Repeat until the rebase completes

Do this autonomously. Only ask the user if a conflict is genuinely ambiguous (e.g. both sides made substantive, incompatible changes to the same logic).

## Step 4: Run the tests

```
uv run pytest -x -q
```

If tests fail, read the failures, fix the issues, and re-run. Keep going until all tests pass. If you cannot resolve a failure after 3 attempts, stop and report the issue to the user.

## Step 5: Run pre-commit hooks

```
uv run pre-commit run --all-files
```

Fix any failures and re-run until clean.

## Step 6: Summarize

Provide a summary of:
- How many commits were replayed
- Any conflicts that were resolved (and how)
- Any test failures that were fixed

## Step 7: Suggest force-push

Ask the user if they would like to force-push the rebased branch:

```
git push --force-with-lease
```

Do NOT push without explicit confirmation.
