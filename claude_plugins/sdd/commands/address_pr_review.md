Look at the code review comments on the PR and address all issues.

## Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps.

## Step 1: Fetch all review comments

Read `Fetch PR comments` under `## PR Hooks` in `.claude/sdd/config.md` (`config.local.md` wins).

- A non-blank value is a script path: run it from the project root. It prints the JSON described
  below.
- A blank value, or an absent section or file, means the project has no such script. Fetch the
  comments with `gh` directly: `gh pr view --json number,headRepository,headRepositoryOwner` for
  the PR number and repo, then `gh api repos/<owner>/<repo>/issues/<n>/comments`,
  `gh api repos/<owner>/<repo>/pulls/<n>/reviews` and
  `gh api repos/<owner>/<repo>/pulls/<n>/comments`. An inline comment whose `position` is null
  is outdated.

If there is no PR for the current branch, tell the user and stop.

Either way you end up with JSON containing:
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
3. If you think it should NOT be addressed: skip it and record the reason for the Step 7 summary.

## Step 5: Run the targeted tier

Read `claude_plugins/sdd/commands/protected/run_test_tier.md` and follow it with `<tier>`: `targeted` and `<diff>`: `--working-tree`. A failure follows "When a targeted run or full run fails" in the tier definition the helper names. CI re-runs the whole suite on the pushed PR and is the backstop, so the local run is feedback on the review fixes.

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
