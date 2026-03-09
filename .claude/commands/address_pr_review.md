Look at the code review comments on the PR and address all issues.

## Step 1: Find the PR

Find the PR for the current branch:

```
gh pr list --head $(git branch --show-current) --json number,title,url
```

If no PR is found, tell the user and stop.

## Step 2: Fetch all review comments

Extract the owner/repo from `gh repo view --json nameWithOwner`.

There are three types of comments on a PR. Fetch all three:

### 2a. Issue-level comments (general PR conversation)

```
gh api repos/{owner}/{repo}/issues/{pr_number}/comments
```

### 2b. Review bodies (top-level review summaries with state like APPROVED, CHANGES_REQUESTED, COMMENTED)

```
gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews
```

### 2c. Inline review comments (comments on specific lines of code)

```
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments
```

For inline comments, check the `position` field to determine staleness:
- If `position` is non-null, the comment is **current** (still applies to the latest diff)
- If `position` is null but `original_position` is non-null, the comment is **outdated/stale** (the code has changed since the comment was made)

Focus on current (non-stale) comments. Mention stale comments only if they raise issues that still appear relevant to the current code.

## Step 3: Identify actionable issues

Read through all comments and compile a list of issues raised. For each issue, classify it as:

- **Bug/Correctness** — something that is wrong or could cause incorrect behavior
- **Design/Architecture** — structural improvement
- **Performance** — efficiency concern
- **Code Quality** — style, naming, conventions
- **Minor/Nit** — low-priority suggestions

Ignore comments that are purely positive feedback ("what looks good" sections).

## Step 4: Read the current code

Before making any changes, read the files mentioned in the review comments to understand the current state. Many issues from earlier review rounds may have already been addressed.

## Step 5: Address each issue

For each actionable issue that has NOT already been fixed:

1. State the issue clearly
2. If you think it should be addressed: fix it immediately
3. If you think it should NOT be addressed: explain why and ask the user for confirmation before skipping

## Step 6: Run tests

After making all changes, run the full test suite:

```
uv run pytest -x -q
```

Fix any failures.

## Step 7: Run the pre-commit

Now make sure that the pre-commit passes:

```
uv run pre-commit
```

Fix any failures.

## Step 8: Summarize

Provide a clear summary of:
- What was fixed
- What was already addressed in previous rounds
- Any issues intentionally skipped (with reasoning)
