---
description: Helper — run a test tier through the project's tier definition and report the result
allowed-tools: Bash, Read, Glob, Grep
---

This is a helper command. A caller reads it and follows its steps inline, so it runs on the
caller's model and tool grants.

Inputs from the caller: `<tier>` (`targeted`, `full` or `checkpoint`) and, for `targeted`,
`<diff>`: the selection arguments the tier definition accepts. `checkpoint` works out its own tier
and `<diff>`, so a caller passes none.

## Step 1: Find the tier definition

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists; its values take
precedence). Under `## Test Hooks`, look at the `Test tiers` value. For `checkpoint`, read the
definition now but run nothing until Step 2 names the tier.

- a non-blank path → read that file and run `<tier>` as it says, with `<diff>` as the diff
  arguments.
- blank, or the file or section absent → run `uv run pytest` with the Bash tool's
  `run_in_background: true` and wait for the completion notification. Treat the result as
  `tier: full`. This project has no tier definition, so this plain run is the only test run it
  has.

## Step 2: Resolve the checkpoint tier

Applies only to `<tier>`: `checkpoint`. Skip it for any other tier.

`<selector>` is the command the tier definition's `targeted` tier runs to choose tests, without
its diff arguments. With no tier definition, omit `--selector`.

```
python3 claude_plugins/sdd/scripts/full_run_record.py resolve --selector "<selector>"
```

The `tier:` line names the tier to run and the `diff:` line is its `<diff>`. Run that tier as
Step 1 describes (the plain run when there is no tier definition). `none` runs nothing.

## Step 3: Record a full run

After any `full` tier finishes, whoever asked for it, record it. `<verdict>` is `pass` when the
tier definition's verdict is a pass, `incomplete` when it reports unfinished tests, and `fail`
otherwise.

```
python3 claude_plugins/sdd/scripts/full_run_record.py write --verdict <verdict>
```

## Step 4: Report

The verdict line is the one the tier definition names for reporting. When it names none, use the
final pytest summary line.

Return the line below. Fixing a failure belongs to the caller; this helper only runs and reports.

```
tier: none|targeted|full · summary: <the verdict line, or "no tests run">
```

`tier:` names the tier that ran. For a checkpoint, the summary starts with the resolver's `why:`:
`tier: none · summary: no test-visible change since full green at abc1234`, or
`tier: targeted · summary: range abc1234..HEAD: <verdict line>`. A `none` summary never contains
the word "passed": nothing ran.
