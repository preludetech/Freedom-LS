Review all open Dependabot PRs and produce an actionable report.

## Step 1: Fetch open Dependabot PRs

Run this command to list all open PRs authored by Dependabot:

```
gh pr list --author "app/dependabot" --state open --json number,title,url,createdAt,labels,headRefName,body --limit 100
```

If there are no open Dependabot PRs, tell the user and stop.

## Step 2: Inspect each PR

For each PR, gather the following information:

1. **What package is being updated?** Extract the package name and version change (from -> to) from the title and body.
2. **Is this a major, minor, or patch bump?** Determine from the version numbers.
3. **What does the changelog say?** Dependabot includes a changelog summary in the PR body — read it.
4. **Are CI checks passing?** Run:
   ```
   gh pr checks <PR_NUMBER>
   ```
5. **Are there merge conflicts?** Check the `mergeable` state:
   ```
   gh pr view <PR_NUMBER> --json mergeable,mergeStateStatus
   ```
6. **Is this a dev-only dependency or a production dependency?** Check the PR body and the package name to determine if this is a development/CI tool (e.g. linters, test frameworks, GitHub Actions, type stubs) vs a runtime dependency.
7. **Are there any breaking changes mentioned?** Look for "BREAKING" or "breaking change" in the changelog/release notes in the PR body.

## Step 3: Assess each PR

Categorise each PR into one of the following:

### Safe to merge
- CI is green
- No merge conflicts
- Patch or minor version bump with no breaking changes
- OR: major bump of a dev-only dependency with no breaking changes

### Needs closer review
- Major version bump of a production dependency
- Breaking changes mentioned in the changelog
- The update touches security-sensitive packages (e.g. auth, crypto, session, CORS)

### Should be closed
- Superseded by a newer Dependabot PR for the same package (Dependabot often opens multiple PRs)
- Updates a package that has been removed from the project

### Needs action before merge
- CI is failing — describe what failed
- Has merge conflicts — note that a rebase is needed
- Has been open for a long time (>30 days) — flag for staleness

## Step 4: Produce the report

Output a structured report in this format:

```
## Dependabot PR Review Report

**Date:** <today's date>
**Total open PRs:** <count>

### Safe to merge
| PR | Package | Change | Notes |
|----|---------|--------|-------|
| #123 | package-name | 1.2.3 -> 1.2.4 | Patch bump, CI green |

### Needs closer review
| PR | Package | Change | Risk |
|----|---------|--------|------|
| #456 | package-name | 2.x -> 3.x | Major bump, breaking changes in auth module |

### Should be closed
| PR | Package | Reason |
|----|---------|--------|
| #789 | package-name | Superseded by #790 |

### Needs action before merge
| PR | Package | Action needed |
|----|---------|---------------|
| #101 | package-name | CI failing: test_foo assertion error |
```

After the table, add a **Recommended actions** section with numbered steps the user should take, prioritised by risk (close superseded PRs first, then merge safe ones, then address failures, then review risky ones).

## Step 5: Offer to take action

Ask the user if they would like you to:

1. **Merge** any of the "Safe to merge" PRs (use `gh pr merge <number> --squash`)
2. **Close** any of the "Should be closed" PRs (use `gh pr close <number>`)
3. **Rebase** any PRs with merge conflicts (use `gh pr comment <number> --body "@dependabot rebase"`)

Do NOT take any of these actions without explicit confirmation from the user.
