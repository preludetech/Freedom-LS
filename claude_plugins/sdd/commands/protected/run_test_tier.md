---
description: Helper — run a test tier through the project's tier definition and report the result
allowed-tools: Bash, Read, Glob, Grep
---

This is a helper command. A caller reads it and follows its steps inline, so it runs on the
caller's model and tool grants.

Inputs from the caller: `<tier>` (`targeted` or `full`) and, for `targeted`, `<diff>`: the
selection arguments the tier definition accepts.

## Step 1: Find the tier definition

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists; its values take
precedence). Under `## Test Hooks`, look at the `Test tiers` value:

- a non-blank path → read that file and run `<tier>` as it says, with `<diff>` as the diff
  arguments.
- blank, or the file or section absent → run `uv run pytest` with the Bash tool's
  `run_in_background: true` and wait for the completion notification. Treat the result as
  `tier: full`. This project has no tier definition, so this plain run is the only test run it
  has.

## Step 2: Report

Return the line below. Fixing a failure belongs to the caller; this helper only runs and reports.

```
tier: none|targeted|full · summary: <the final pytest summary line, or "no tests run">
```
