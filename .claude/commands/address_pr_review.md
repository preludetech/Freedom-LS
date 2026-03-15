Look at the code review comments on the PR and address all issues.

## Step 1: Fetch all review comments

Run the script to fetch all PR comments:

```
./fetch_pr_comments.sh
```

If the script reports no PR found, tell the user and stop.

The script outputs JSON containing:
- `issue_comments` — general PR conversation comments
- `reviews` — top-level review summaries (APPROVED, CHANGES_REQUESTED, COMMENTED)
- `inline_comments` — comments on specific lines of code, with an `is_outdated` field

Focus on current (non-outdated) inline comments. Mention outdated comments only if they raise issues that still appear relevant to the current code.

## Step 2: Identify actionable issues

Read through all comments and compile a list of issues raised. For each issue, classify it as:

- **Bug/Correctness** — something that is wrong or could cause incorrect behavior
- **Design/Architecture** — structural improvement
- **Performance** — efficiency concern
- **Code Quality** — style, naming, conventions
- **Minor/Nit** — low-priority suggestions

Ignore comments that are purely positive feedback ("what looks good" sections).

## Step 3: Read the current code

Before making any changes, read the files mentioned in the review comments to understand the current state. Many issues from earlier review rounds may have already been addressed.

## Step 4: Address each issue

For each actionable issue that has NOT already been fixed:

1. State the issue clearly
2. If you think it should be addressed: fix it immediately
3. If you think it should NOT be addressed: explain why and ask the user for confirmation before skipping

## Step 5: Run tests

After making all changes, run the full test suite:

```
uv run pytest -x -q
```

Fix any failures.

## Step 6: Run the pre-commit

Now make sure that the pre-commit passes:

```
uv run pre-commit
```

Fix any failures.

## Step 7: Summarize

Provide a clear summary of:
- What was fixed
- What was already addressed in previous rounds
- Any issues intentionally skipped (with reasoning)
