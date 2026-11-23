---
description: Helper — run the project's tests through its Test runner hook and report the result
allowed-tools: Bash, Read, Glob, Grep
---

This is a helper command. A caller reads it and follows its steps inline, so it runs on the
caller's model and tool grants.

The project owns how its tests run. This helper passes one request to the project's test runner
and returns the runner's answer.

## The request

The caller passes one request and its inputs:

| Request | Inputs | Asks for |
| --- | --- | --- |
| `change` | `<change>`; optional `<widen>: no` | The tests that cover `<change>` |
| `everything` | | The whole suite |
| `before landing` | optional `<prepare>` | Whatever proves the branch is safe to land |
| `one test` | `<test>` | That test alone |
| `failed` | `<failed>`; `<change>` | The tests an earlier run left failing, after a fix |

- `<change>` is `uncommitted` (the work not yet committed), `paths <path…>` or
  `commits <a>..<b>`. With `failed`, it is the change the fix made.
- `<widen>: no` tells the runner to run nothing when covering `<change>` takes the whole suite.
- `<prepare>` is a script the runner runs before any test it starts, and skips when it runs
  nothing.
- `<failed>` is the `failed:` value an earlier run returned, passed back unchanged. `<test>` is
  one id from it, or a test the caller wrote, named the way the project's testing skills name one.

## Step 1: Find the test runner

Read `Test runner` under `## Test Hooks` in `.claude/sdd/config.md` (`config.local.md` wins).

- blank, or the key, section or file absent → return
  `status: blocked · reason: no Test runner hook in .claude/sdd/config.md` and stop.
- a non-blank path → read that file and follow it with the request and its inputs. The file
  decides which tests run and how.

## Step 2: Report

Return the runner's line. Fixing a failure belongs to the caller.

```
tests: passed|failed|incomplete|nothing to run|needs everything · summary: <the runner's verdict line> · failed: <test ids>
```

- `incomplete`: the runner could not finish the run. It is an environment problem to report, with
  no test to fix.
- `nothing to run`: the runner found no test the request covers. The summary says why and never
  reads as a pass.
- `needs everything`: returned only under `<widen>: no`. Nothing ran.
- `failed:` appears only on `tests: failed`. The ids are the runner's own; pass them back as it
  wrote them.

## When a run fails

This section addresses the agent that owns the change. A mechanic briefed only to run tests
returns the line above and stops.

Fix the failure, then follow this helper again with the request `failed`, `<failed>`: the set the
failed run returned, and `<change>`: what the fix changed. An uncommitted fix is `paths` with the
files it edited. A committed fix is `commits <sha before the fix>..HEAD`. Done when that run returns
`tests: passed`. A failure in it is fixed the same way, with its own `failed:` set and the new
fix's change.
