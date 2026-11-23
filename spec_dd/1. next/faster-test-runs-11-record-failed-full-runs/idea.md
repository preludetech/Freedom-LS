# A failed full run is not repeated in full

Spec 11 of 13 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** one full run, 25 minutes at 4 workers, for each full run that fails while a worktree is being finished.

## What

When a full run fails, the run records the tests that failed and the commit it tested. After
the fix, the next checkpoint runs those tests and a targeted run over the fix. It does not run the
whole suite again.

## Why

A full run is 17,570 tests. When one of them fails, the run records nothing, and `finish_worktree`
follows the failed run again from its start, so a single flaky test costs a second full run. Main
takes about 140 commits a day, so it usually moves during that second run and the main-moved loop
takes another pass. Every test that passed in the failed run passed on a known commit, and the
next run throws that result away.

## What is settled

- The full-run record holds the commit a full run tested and the tests that failed on it. A
  passing run is a record with no failed tests.
- A checkpoint after a failed full run runs the recorded failed tests, plus what the selector
  picks for the diff since the recorded commit.
- A recorded failed test stays in every later checkpoint until it passes.
- A run that left tests unfinished records nothing, and the next checkpoint is a full run.
- This applies to the `finish_worktree` checkpoint, in Step 1 and in the main-moved loop, and to
  `implement_plan`'s final full run.
- A test that passes only after being fixed twice is still a real failure, as it is today.
- The record stays one file per branch in the worktree and is never committed.

## Open until the spec

- Whether a fix that touches an escalation path, such as a `conftest.py`, still resolves to a full
  run.
- Whether the proof runs of a flaky fix count as the re-run of that test.

## Out of scope

- How a flaky test is diagnosed and fixed; the flaky test guide owns that.
- Failures inside a batch; `faster-test-runs-10-rerun-only-failures-in-a-batch` owns them.
- What writes the record; `faster-test-runs-12-reliable-full-run-record` owns that.

## Resources

- `spec_dd/1. next/faster-test-runs/research_finish_worktree_reruns.md`.
- `claude_plugins/django-stack/scripts/full_run_record.py`,
  `claude_plugins/django-stack/resources/test_runner.md`.
- `claude_plugins/sdd/commands/finish_worktree.md`, "Flaky tests" and "Obvious failures".
